#!/usr/bin/env python3
"""
Static Play Store policy scanner for React Native / Expo projects (Android).

Grep-based lead generator for a Google Play policy audit. Read-only:
it never writes to the scanned project.

Usage:
    python3 scan.py /path/to/rn-project
    python3 scan.py /path/to/rn-project --format json > findings.json

Two caveats that matter more here than on iOS:

  1. This reads the SOURCE AndroidManifest. The one that ships is the MERGED
     manifest, and the difference is exactly where transitive permissions hide.
     Build the app, then check android/**/merged_manifests/**/AndroidManifest.xml.
  2. Version floors (target API level, Play Billing Library) advance every
     August. Verify anything this reports as a version blocker against the
     live requirements page before acting on it.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

# Floors as of September 2026 — re-check against the live pages.
TARGET_SDK_NEW_UPLOAD = 36      # Android 16, enforced 31 Aug 2026
TARGET_SDK_DISCOVERABILITY = 35  # Android 15, floor for existing apps
BILLING_MAJOR_FLOOR = 8          # Play Billing Library 8+, enforced 31 Aug 2026

SKIP_DIRS = {
    "node_modules", ".git", "build", "DerivedData", "Pods", ".expo",
    ".next", "dist", "coverage", "vendor", ".gradle", ".idea", "__pycache__",
    "ios",  # Android-only audit
}
CODE_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".json", ".xml", ".gradle", ".kts",
    ".java", ".kt", ".properties", ".env", ".pro",
}
# Firebase config files are public client identifiers, meant to be committed.
# Flagging them BLOCKER fired on 47 projects and trained teams to ignore the rule.
PUBLIC_CONFIG = re.compile(r"google-services\.json$", re.I)

# Source sets that are never part of a Play upload.
DEBUG_VARIANT = re.compile(r"/src/(debug|androidTest|test)/")

TEST_HINT = re.compile(
    r"(__tests__|__mocks__|\.test\.|\.spec\.|\.stories\.|/mocks?/|/fixtures?/|"
    r"[Ss]torybook/|e2e/|\.e2e\.)", re.I)

# id, severity, policy, description, regex, extension filter (None = all)
RULES = [
    ("SECRET-HARDCODED", "BLOCKER", "Device & Network Abuse",
     "Possible hardcoded credential — the JS bundle and strings.xml are extractable from the AAB",
     re.compile(r"""(sk_live_|sk_test_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_\-]{30,}|"""
                r"""AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"""
                r"""(?i:(api[_-]?key|secret|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]))"""),
     None),

    ("DYNAMIC-CODE", "BLOCKER", "Device & Network Abuse",
     "Dynamic code execution — downloading or executing code outside Play is prohibited",
     re.compile(r"\beval\s*\(|new\s+Function\s*\(|DexClassLoader|PathClassLoader\s*\(|vm\.runInNewContext"),
     None),

    ("EXTERNAL-PAYMENT", "BLOCKER", "Payments",
     "Possible external payment path for digital goods — confirm the SKU is a physical good or real-world service, "
     "or that an alternative-billing program covers it",
     re.compile(r"(?i)(openURL|Linking\.openURL|WebView[^\n]{0,80})[^\n]{0,120}"
                r"(stripe\.com|checkout\.stripe|paypal\.com|buy\.stripe|paddle\.com|lemonsqueezy|"
                r"/checkout|/upgrade|/subscribe|/billing)"),
     None),

    ("PAYMENT-SDK", "HIGH", "Payments",
     "Third-party payment SDK present — must not serve digital goods unless an alternative-billing program applies",
     re.compile(r"@stripe/stripe-react-native|react-native-paypal|react-native-braintree|"
                r"braintree-web-drop-in|react-native-razorpay|@paddle/paddle-js"),
     None),

    ("CLEARTEXT", "HIGH", "Device & Network Abuse",
     "Cleartext HTTP traffic enabled — use a scoped network security config if an exception is genuinely needed",
     re.compile(r"usesCleartextTraffic\s*=\s*[\"']true[\"']|cleartextTrafficPermitted\s*=\s*[\"']true[\"']"),
     None),

    ("ALLOW-BACKUP", "MEDIUM", "User Data",
     "android:allowBackup is enabled — app data can reach the user's cloud backup; disable or scope it if the app holds sensitive data",
     re.compile(r"android:allowBackup\s*=\s*[\"']true[\"']"),
     {".xml"}),

    ("INSECURE-STORAGE", "HIGH", "User Data",
     "Token or personal data in AsyncStorage (unencrypted on disk) — use EncryptedSharedPreferences / Keystore",
     re.compile(r"AsyncStorage\.setItem\s*\(\s*['\"][^'\"]*(token|auth|password|secret|session|patient|phi|ssn|dob|mrn|card)"),
     None),

    ("TRACKING-SDK", "MEDIUM", "Data safety",
     "Tracking / analytics / ads SDK — must appear in the Data safety form, and AD_ID must be declared if used",
     re.compile(r"react-native-fbsdk|@react-native-firebase/analytics|react-native-appsflyer|"
                r"react-native-adjust|react-native-branch|react-native-applovin-max|"
                r"react-native-google-mobile-ads|"
                r"@amplitude/|mixpanel-react-native|@segment/analytics|react-native-onesignal"),
     {".json", ".ts", ".tsx", ".js", ".jsx"}),

    ("CLIENT-ENTITLEMENT", "HIGH", "Payments",
     "Purchase entitlement possibly trusted from local storage — verify the purchase token with the Play Developer API server-side",
     re.compile(r"(?i)(AsyncStorage|localStorage)[^\n]{0,60}(isPremium|isPro|['\"]pro['\"]|subscribed|entitle)"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("CRASH-PII", "HIGH", "Data safety",
     "Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in Data safety",
     re.compile(r"(?i)(Sentry\.(setContext|setUser|setExtra)|Bugsnag\.(setUser|addMetadata)|"
                r"crashlytics\(\)\.set|logEvent)\s*\([^)]{0,120}\b(mrn|patient|dob|ssn|diagnos|email|phone|(?:user|full|first|last|real|patient)_?name)\b"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("WEBVIEW-SHELL", "MEDIUM", "Spam & Minimum Functionality",
     "WebView usage — if it is the primary surface, the app may be judged a repackaged website",
     re.compile(r"<WebView|from\s+['\"]react-native-webview['\"]"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("OTA-UPDATES", "MEDIUM", "Device & Network Abuse",
     "OTA update channel — permitted for fixes and content, not for shipping unreviewed behavior",
     re.compile(r"expo-updates|react-native-code-push|CodePush"),
     {".json", ".ts", ".tsx", ".js", ".jsx"}),

    ("CONSOLE-LOG", "LOW", "Quality · PII leakage risk",
     "console logging in source — strip from release paths and check it never logs personal data",
     re.compile(r"\bconsole\.(log|debug|info)\s*\("),
     {".ts", ".tsx", ".js", ".jsx"}),
]

# permission -> (severity, why)
PERMISSIONS = {
    "ACCESS_BACKGROUND_LOCATION": ("HIGH", "Requires a Console declaration plus a demo video; only for features that need location while the app is closed"),
    "QUERY_ALL_PACKAGES": ("HIGH", "Restricted; allowed only for a narrow set of use cases and usually pulled in transitively"),
    "MANAGE_EXTERNAL_STORAGE": ("HIGH", "Restricted; use scoped storage or the Storage Access Framework"),
    "READ_SMS": ("HIGH", "Restricted; use the SMS Retriever API for OTP"),
    "RECEIVE_SMS": ("HIGH", "Restricted permission"),
    "SEND_SMS": ("HIGH", "Restricted permission"),
    "READ_CALL_LOG": ("HIGH", "Restricted permission"),
    "WRITE_CALL_LOG": ("HIGH", "Restricted permission"),
    "PROCESS_OUTGOING_CALLS": ("HIGH", "Restricted permission"),
    "BIND_ACCESSIBILITY_SERVICE": ("HIGH", "Accessibility API misuse is a suspension risk"),
    "REQUEST_INSTALL_PACKAGES": ("HIGH", "Restricted; distributing APKs outside Play violates Device & Network Abuse"),
    "READ_MEDIA_IMAGES": ("MEDIUM", "Photo/video policy: use the system photo picker unless broad access is core functionality"),
    "READ_MEDIA_VIDEO": ("MEDIUM", "Photo/video policy: use the system photo picker unless broad access is core functionality"),
    "READ_EXTERNAL_STORAGE": ("MEDIUM", "Prefer scoped storage or the photo picker"),
    "WRITE_EXTERNAL_STORAGE": ("MEDIUM", "Deprecated; prefer scoped storage"),
    "READ_PHONE_STATE": ("MEDIUM", "Often added transitively by device-info libraries; remove if unused"),
    "READ_CONTACTS": ("MEDIUM", "Justify against core functionality; a contact picker avoids the permission"),
    "ACCESS_FINE_LOCATION": ("MEDIUM", "Justify precise location; coarse location or a one-time picker is often enough"),
    "SYSTEM_ALERT_WINDOW": ("MEDIUM", "Overlay permission draws policy scrutiny"),
    "AD_ID": ("MEDIUM", "Must be declared when used on API 33+; must be ABSENT in child-directed apps"),
    "PACKAGE_USAGE_STATS": ("HIGH", "Restricted; requires a qualifying use case"),
    "RECORD_AUDIO": ("MEDIUM", "Must map to a visible feature; background use needs a foreground service type"),
}


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in CODE_EXT or fn in {"AndroidManifest.xml", ".env", "gradle.properties"}:
                yield os.path.join(dirpath, fn)


def scan_patterns(root, findings):
    for path in iter_files(root):
        ext = os.path.splitext(path)[1].lower()
        rel = os.path.relpath(path, root)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        if len(lines) > 20000:
            continue
        is_test = bool(TEST_HINT.search(rel))
        is_public_config = bool(PUBLIC_CONFIG.search(os.path.basename(path)))
        is_debug_only = bool(DEBUG_VARIANT.search(rel.replace(os.sep, "/")))
        for rule_id, sev, policy, desc, rx, exts in RULES:
            if exts and ext not in exts:
                continue
            if is_public_config and rule_id == "SECRET-HARDCODED":
                continue
            for i, line in enumerate(lines, 1):
                if len(line) > 2000:
                    continue
                if rx.search(line):
                    effective, note = sev, ""
                    if is_test and sev in ("BLOCKER", "HIGH"):
                        effective, note = "LOW", " [in a test/fixture path — verify]"
                    elif is_debug_only and sev in ("BLOCKER", "HIGH"):
                        # debug source sets never ship to Play; the RN template puts
                        # cleartext here so Metro can connect.
                        effective = "INFO"
                        note = " [debug source set only — does not ship]"
                    findings.append({
                        "id": rule_id, "severity": effective, "policy": policy,
                        "description": desc + note,
                        "file": rel, "line": i, "evidence": line.strip()[:180],
                    })


def scan_manifests(root, findings):
    merged_seen = False
    for dirpath, dirnames, filenames in os.walk(root):
        # SKIP_DIRS prunes 'build', but the merged manifest — the one that
        # actually ships — only exists under it. Keep that one path open, and
        # accept both the singular and plural spellings AGP has used.
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS
                       or d.startswith("merged_manifest")
                       or (d == "build" and os.path.basename(dirpath) == "app")
                       or os.path.basename(dirpath) in ("build", "intermediates")]
        for fn in filenames:
            if fn != "AndroidManifest.xml":
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            if "merged_manifest" in rel:
                merged_seen = True
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                m = re.search(
                    r'android:name="(?:android\.permission|com\.google\.android\.gms\.permission)\.([A-Z_]+)"',
                    line)
                if not m:
                    continue
                perm = m.group(1)
                if perm in PERMISSIONS and "tools:node=\"remove\"" not in line:
                    sev, why = PERMISSIONS[perm]
                    findings.append({
                        "id": f"PERM-{perm}", "severity": sev, "policy": "Permissions",
                        "description": why, "file": rel, "line": i, "evidence": line.strip()[:180],
                    })
            if "FOREGROUND_SERVICE" in text and "<service" in text and "foregroundServiceType" not in text:
                findings.append({
                    "id": "FGS-TYPE-MISSING", "severity": "HIGH", "policy": "Android 14+ foreground services",
                    "description": "Foreground service permission and a service declared, but no foregroundServiceType. "
                                   "Android 14+ requires a declared type plus its matching permission, and Play requires "
                                   "a Console justification.",
                    "file": rel, "line": 0, "evidence": "",
                })
    if not merged_seen:
        findings.append({
            "id": "MERGED-MANIFEST-NOT-CHECKED", "severity": "MEDIUM", "policy": "Permissions",
            "description": "Only the source manifest was scanned — no merged manifest found. Build the app and re-check "
                           "android/**/merged_manifests/**/AndroidManifest.xml; libraries add permissions you never requested.",
            "file": "android/", "line": 0, "evidence": "",
        })


def scan_build_config(root, findings):
    def read(p):
        try:
            return open(os.path.join(root, p), encoding="utf-8", errors="ignore").read()
        except OSError:
            return ""

    gradle = read("android/build.gradle") + read("android/app/build.gradle") \
        + read("android/build.gradle.kts") + read("android/app/build.gradle.kts")
    expo_cfg = read("app.json") + read("app.config.js") + read("app.config.ts")

    # target API level
    m = re.search(r"targetSdkVersion\s*[=:]?\s*[\"']?(\d+)", gradle + expo_cfg)
    if m:
        target = int(m.group(1))
        if target < TARGET_SDK_DISCOVERABILITY:
            sev = "BLOCKER"      # below the floor: existing app loses discoverability too
        elif target < TARGET_SDK_NEW_UPLOAD:
            sev = "HIGH"         # shipped app keeps working; only new uploads are blocked
        else:
            sev = None
        if sev:
            findings.append({
                "id": "TARGET-SDK", "severity": sev, "policy": "Target API level requirement",
                "description": f"targetSdkVersion is {target}. New uploads and updates need API "
                               f"{TARGET_SDK_NEW_UPLOAD}+ (enforced 31 Aug 2026); existing apps need at least "
                               f"API {TARGET_SDK_DISCOVERABILITY} to stay discoverable. Raising it also makes "
                               f"edge-to-edge mandatory and stops onBackPressed firing — budget for that work. "
                               f"Verify the current floor on the live requirements page.",
                "file": "android/**/build.gradle", "line": 0, "evidence": m.group(0),
            })
    elif gradle or expo_cfg:
        findings.append({
            "id": "TARGET-SDK-UNKNOWN", "severity": "MEDIUM", "policy": "Target API level requirement",
            "description": "Could not determine targetSdkVersion — check the value resolved by the RN gradle plugin "
                           "or expo-build-properties",
            "file": "android/build.gradle", "line": 0, "evidence": "",
        })

    # Play Billing Library version
    pkg = read("package.json")
    if re.search(r"react-native-iap|react-native-purchases|expo-in-app-purchases", pkg):
        bill = re.search(r"billingclient[:\s\"']*(?:billing[:\s\"']*)?(\d+)\.", gradle)
        if bill and int(bill.group(1)) < BILLING_MAJOR_FLOOR:
            findings.append({
                "id": "BILLING-VERSION", "severity": "BLOCKER", "policy": "Play Billing Library deprecation",
                "description": f"Play Billing Library {bill.group(1)}.x detected; the floor moved to "
                               f"{BILLING_MAJOR_FLOOR}+ on 31 Aug 2026 (extension route to 1 Nov 2026). "
                               f"The version is pinned by your RN billing wrapper — upgrade the package, not gradle.",
                "file": "android/app/build.gradle", "line": 0, "evidence": bill.group(0),
            })
        else:
            findings.append({
                "id": "BILLING-VERIFY", "severity": "MEDIUM", "policy": "Play Billing Library deprecation",
                "description": f"Billing wrapper present — confirm the pinned Play Billing Library major version meets "
                               f"the current floor ({BILLING_MAJOR_FLOOR}+ as of Aug 2026). Check the wrapper's own "
                               f"android/build.gradle under node_modules.",
                "file": "package.json", "line": 0, "evidence": "",
            })

    # AAB vs APK
    ci = ""
    for p in ("fastlane/Fastfile", "android/fastlane/Fastfile", "ios/fastlane/Fastfile",
              ".github/workflows", ".gitlab-ci.yml", "bitrise.yml", "codemagic.yaml",
              "Jenkinsfile", "eas.json", "Makefile"):
        full = os.path.join(root, p)
        if os.path.isfile(full):
            ci += read(p)
        elif os.path.isdir(full):
            for dirpath, _, filenames in os.walk(full):
                for fn in filenames:
                    try:
                        ci += open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
                    except OSError:
                        pass
    builds_apk = "assembleRelease" in ci or re.search(
        r'task:\s*["\']assemble["\']', ci)
    builds_aab = "bundleRelease" in ci or "app-bundle" in ci or re.search(
        r'task:\s*["\']bundle["\']', ci)
    if ci and builds_apk and not builds_aab:
        findings.append({
            "id": "APK-NOT-AAB", "severity": "BLOCKER", "policy": "App Bundle requirement",
            "description": "Release pipeline builds an APK (assemble) with no bundle task. Play requires an "
                           "Android App Bundle for new apps and updates. If this pipeline only feeds "
                           "internal distribution (Firebase App Distribution, ad-hoc QA), that is fine — "
                           "confirm it is not the Play upload path.",
            "file": "(ci config)", "line": 0, "evidence": "assembleRelease",
        })

    # 16 KB page alignment — presence of native libs is the lead
    sos = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "android")):
        dirnames[:] = [d for d in dirnames if d not in {".gradle", ".idea"}]
        for fn in filenames:
            if fn.endswith(".so"):
                sos.append(os.path.relpath(os.path.join(dirpath, fn), root))
    if sos:
        findings.append({
            "id": "PAGE-SIZE-16KB", "severity": "MEDIUM", "policy": "16 KB page size support",
            "description": f"{len(sos)} native library file(s) in the build output. Each must be built for 16 KB page "
                           f"alignment (NDK r27+) or Play warns and eventually blocks. Check with "
                           f"`llvm-readelf --program-headers <lib>.so | grep LOAD` and upgrade the owning RN dependency. "
                           f"One stale .so from an unmaintained SDK blocks the whole release — find it early.",
            "file": sos[0], "line": 0, "evidence": ", ".join(os.path.basename(s) for s in sos[:6]),
        })


def scan_bare_rn(root, findings):
    """Checks that only apply to bare RN (CLI) projects, where android/ is checked in."""
    android = os.path.join(root, "android")
    if not os.path.isdir(android):
        return

    def read_rel(*parts):
        try:
            return open(os.path.join(android, *parts), encoding="utf-8", errors="ignore").read()
        except OSError:
            return ""

    gradle = read_rel("build.gradle") + read_rel("build.gradle.kts") \
        + read_rel("app", "build.gradle") + read_rel("app", "build.gradle.kts")
    props = read_rel("gradle.properties")

    # --- NDK version decides 16 KB page alignment of anything you compile
    m = re.search(r"ndkVersion\s*[=:]?\s*[\"']([\d.]+)", gradle)
    if m:
        try:
            major = int(m.group(1).split(".")[0])
        except ValueError:
            major = None
        if major is not None and major < 27:
            findings.append({
                "id": "NDK-VERSION", "severity": "HIGH", "policy": "16 KB page size support",
                "description": f"ndkVersion is {m.group(1)}. 16 KB page alignment requires NDK r27+. "
                               f"Anything compiled with an older NDK ships unaligned, which Play warns on "
                               f"and eventually blocks. Bare RN projects pin this directly — managed Expo "
                               f"does not expose it.",
                "file": "android/build.gradle", "line": 0, "evidence": m.group(0),
            })

    # --- Signing secrets committed to the repo
    for label, text, path in (("gradle.properties", props, "android/gradle.properties"),
                              ("build.gradle", gradle, "android/app/build.gradle")):
        for m in re.finditer(
                r"(?i)(store_?password|key_?password|key_?alias)\s*[=:\s]\s*[\"']?([^\s\"'#]{3,})", text):
            if m.group(2).startswith(("$", "System.", "project.")):
                continue
            findings.append({
                "id": "SIGNING-SECRET-COMMITTED", "severity": "HIGH", "policy": "Device & Network Abuse",
                "description": f"A signing credential appears to be hardcoded in {label}. Anyone with the "
                               f"repo can sign builds as you. Move it to an environment variable or a "
                               f"local.properties file that is gitignored. Rotate the keystore password "
                               f"if this has ever been pushed.",
                "file": path, "line": text[:m.start()].count("\n") + 1,
                "evidence": m.group(1) + "=<redacted>",
            })

    # --- local.properties should never be committed
    if os.path.isfile(os.path.join(android, "local.properties")):
        gitignore = ""
        try:
            gitignore = open(os.path.join(root, ".gitignore"), encoding="utf-8", errors="ignore").read()
        except OSError:
            pass
        if "local.properties" not in gitignore:
            findings.append({
                "id": "LOCAL-PROPERTIES-TRACKED", "severity": "MEDIUM", "policy": "Quality",
                "description": "android/local.properties exists and is not in .gitignore. It holds machine-"
                               "specific SDK paths and sometimes credentials; it should not be committed.",
                "file": "android/local.properties", "line": 0, "evidence": "",
            })


def scan_toolchain(root, findings):
    """The Android Gradle Plugin version decides whether the rest of the advice
    is applicable at all. AGP below 3.2 cannot produce an App Bundle, and below
    7.x cannot compile against a modern API level — so "raise targetSdkVersion"
    is not a fix that can be applied, it is a build-system migration."""
    gradle = ""
    for rel in ("android/build.gradle", "android/build.gradle.kts"):
        try:
            gradle += open(os.path.join(root, rel), encoding="utf-8", errors="ignore").read()
        except OSError:
            pass
    m = re.search(r"com\.android\.tools\.build:gradle[:\"']+(\d+)\.(\d+)", gradle)
    if not m:
        return
    major, minor = int(m.group(1)), int(m.group(2))
    if major >= 7:
        return
    cannot_bundle = (major, minor) < (3, 2)
    findings.append({
        "id": "AGP-TOO-OLD", "severity": "BLOCKER",
        "policy": "App Bundle requirement / Target API level",
        "description": f"Android Gradle Plugin {major}.{minor} is too old to ship. "
                       + ("It predates the App Bundle format entirely, so no AAB can be produced. "
                          if cannot_bundle else
                          "It cannot compile against a current compileSdk. ")
                       + "Any targetSdkVersion finding on this project is blocked behind a build-system "
                         "upgrade (AGP, Gradle wrapper, dependency syntax) — budget that work first "
                         "rather than treating the API level as a one-line change.",
        "file": "android/build.gradle", "line": gradle[:m.start()].count("\n") + 1,
        "evidence": m.group(0),
    })


def scan_abi_and_signing(root, findings):
    """Two upload-time gates the scanner had no way to produce.

    64-bit has been mandatory since Aug 2019; an armeabi-v7a-only upload is
    rejected outright. Committed keystores are not a Play gate, but a keystore
    plus its password in the same repo means anyone with clone access can sign
    releases as you — worth more than most policy findings.
    """
    android = os.path.join(root, "android")
    if not os.path.isdir(android):
        return

    def read_rel(*parts):
        try:
            return open(os.path.join(android, *parts), encoding="utf-8", errors="ignore").read()
        except OSError:
            return ""

    gradle = read_rel("build.gradle") + read_rel("app", "build.gradle") \
        + read_rel("build.gradle.kts") + read_rel("app", "build.gradle.kts")
    props = read_rel("gradle.properties")

    # Only judge an explicitly declared ABI list. With nothing declared, RN's
    # defaults already include arm64-v8a, so silence is correct.
    declared = []
    for m in re.finditer(r"abiFilters\s+([^\n}]+)", gradle):
        declared += re.findall(r"[\w-]+", m.group(1))
    m = re.search(r"reactNativeArchitectures\s*=\s*([^\n]+)", props)
    if m:
        declared += [a.strip() for a in m.group(1).split(",")]
    declared = [a for a in declared if a.startswith(("armeabi", "arm64", "x86"))]
    if declared and not any(a.startswith(("arm64", "x86_64")) for a in declared):
        findings.append({
            "id": "ABI-NO-64BIT", "severity": "BLOCKER", "policy": "64-bit requirement",
            "description": f"Native ABIs are restricted to {', '.join(sorted(set(declared)))} with no "
                           f"64-bit architecture. Play has required a 64-bit version of every native "
                           f"library since 1 Aug 2019 and rejects the upload. Add arm64-v8a.",
            "file": "android/app/build.gradle", "line": 0, "evidence": ", ".join(sorted(set(declared))),
        })

    # Keystores tracked in git.
    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True, timeout=30)
        tracked = out.stdout.splitlines() if out.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        tracked = []
    keystores = [f for f in tracked
                 if f.lower().endswith((".jks", ".keystore", ".p12"))
                 and "debug" not in os.path.basename(f).lower()]
    if keystores:
        findings.append({
            "id": "KEYSTORE-COMMITTED", "severity": "HIGH", "policy": "Device & Network Abuse",
            "description": f"{len(keystores)} signing keystore(s) tracked in git. Combined with a password "
                           f"in build.gradle or gradle.properties, anyone who can clone the repo can sign "
                           f"releases as you. Remove from history, rotate, and keep the keystore out of "
                           f"the repo. Note .gitignore does not untrack a file already committed.",
            "file": keystores[0], "line": 0, "evidence": keystores[0],
        })


def scan_structural(root, findings):
    if _grep(root, r"(?i)(signUp|sign_up|createUser|createAccount|registerUser|auth/register)") \
            and not _grep(root, r"(?i)(deleteAccount|delete_account|account/delete|deleteUser|closeAccount)"):
        findings.append({
            "id": "ACCOUNT-DELETION", "severity": "HIGH", "policy": "Account deletion",
            "description": "Account creation found with no in-app deletion path. Play requires deletion available "
                           "in-app AND a publicly accessible web deletion URL declared in Console.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    if _grep(root, r"(?i)(createPost|newComment|sendMessage|uploadPhoto|publishPost|<Feed|postComment)") \
            and not _grep(root, r"(?i)(reportContent|reportPost|reportUser|blockUser|muteUser|flagContent|moderat)"):
        findings.append({
            "id": "UGC-MODERATION", "severity": "HIGH", "policy": "User Generated Content",
            "description": "UGC features found with no report/block/moderation path. Play requires a user agreement, "
                           "in-app reporting, user blocking, and moderation with removal — plus CSAE standards and a "
                           "reporting contact for apps with social features.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    if not _grep(root, r"(?i)(privacy[- _]?policy|privacyPolicyUrl)"):
        findings.append({
            "id": "PRIVACY-POLICY", "severity": "BLOCKER", "policy": "User Data",
            "description": "No privacy policy reference found. A policy URL is required in Play Console and must be "
                           "reachable inside the app.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    if _grep(root, r"react-native-iap|react-native-purchases|expo-in-app-purchases") \
            and not _grep(root, r"(?i)(acknowledgePurchase|finishTransaction|verifyPurchase|purchaseToken)"):
        findings.append({
            "id": "PURCHASE-ACK", "severity": "HIGH", "policy": "Payments",
            "description": "Billing integration found with no purchase acknowledgement or token verification. "
                           "Unacknowledged purchases are auto-refunded after 3 days, and entitlements must be verified "
                           "server-side via the Play Developer API.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # Data safety inventory — always emit, it's a checklist not a violation
    sdks = []
    for name, rx in [
        ("Firebase Analytics", r"@react-native-firebase/analytics"),
        ("Crashlytics", r"@react-native-firebase/crashlytics"),
        ("Sentry", r"@sentry/react-native"),
        ("Bugsnag", r"@bugsnag/react-native"),
        ("Facebook SDK", r"react-native-fbsdk"),
        ("AppsFlyer", r"react-native-appsflyer"),
        ("Adjust", r"react-native-adjust"),
        ("Branch", r"react-native-branch"),
        ("AdMob", r"react-native-google-mobile-ads"),
        ("AppLovin", r"react-native-applovin-max"),
        ("OneSignal", r"react-native-onesignal"),
        ("Amplitude", r"@amplitude"),
        ("Mixpanel", r"mixpanel-react-native"),
        ("Segment", r"@segment/analytics"),
    ]:
        if _grep(root, rx):
            sdks.append(name)
    if sdks:
        findings.append({
            "id": "DATA-SAFETY-INVENTORY", "severity": "MEDIUM", "policy": "Data safety",
            "description": "SDKs that collect data: " + ", ".join(sdks) +
                           ". Every one is a Data safety line item, and the form must match the code. Crash reporters "
                           "are the ones teams forget — they collect device identifiers and often app-usage data.",
            "file": "package.json", "line": 0, "evidence": "",
        })


_grep_cache = {}


def _grep(root, pattern):
    key = (root, pattern)
    if key in _grep_cache:
        return _grep_cache[key]
    rx = re.compile(pattern)
    hit = False
    for path in iter_files(root):
        if os.path.splitext(path)[1].lower() not in {".ts", ".tsx", ".js", ".jsx", ".json", ".xml"}:
            continue
        if TEST_HINT.search(os.path.relpath(path, root)):
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                if rx.search(f.read(400000)):
                    hit = True
                    break
        except OSError:
            continue
    _grep_cache[key] = hit
    return hit


# Rules that describe one condition, not N occurrences: report once with a count.
COLLAPSE_TO_ONE = {"OTA-UPDATES", "WEBVIEW-SHELL", "TRACKING-SDK", "PAYMENT-SDK", "CONSOLE-LOG"}


def dedupe(findings, per_rule_cap=12):
    seen = defaultdict(int)
    out = []
    for f in findings:
        seen[f["id"]] += 1
        cap = 1 if f["id"] in COLLAPSE_TO_ONE else per_rule_cap
        if seen[f["id"]] <= cap:
            out.append(f)
    for rule_id, count in seen.items():
        cap = 1 if rule_id in COLLAPSE_TO_ONE else per_rule_cap
        if count > cap:
            out.append({
                "id": rule_id, "severity": "INFO", "policy": "",
                "description": f"...and {count - cap} more occurrences of {rule_id}",
                "file": "", "line": 0, "evidence": "",
            })
    return out


ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def to_markdown(findings, root):
    counts = defaultdict(int)
    for f in findings:
        counts[f["severity"]] += 1
    out = [f"# Play policy scan — `{root}`", "", "| Severity | Count |", "|---|---|"]
    for sev in ["BLOCKER", "HIGH", "MEDIUM", "LOW"]:
        out.append(f"| {sev} | {counts[sev]} |")
    out += ["", "_Grep-based leads only, read from the SOURCE manifest. Build the app and re-check the merged "
                "manifest for transitive permissions. Verify version floors against the live Play pages._", ""]
    findings.sort(key=lambda f: (ORDER.get(f["severity"], 5), f["id"], f.get("file", "")))
    current = None
    for f in findings:
        if f["severity"] != current:
            current = f["severity"]
            out.append(f"\n## {current}\n")
        loc = f"`{f['file']}:{f['line']}`" if f.get("file") and f.get("line") else (f"`{f['file']}`" if f.get("file") else "")
        out.append(f"- **{f['id']}** {loc} — {f['description']}"
                   + (f"  \n  _{f['policy']}_" if f["policy"] else ""))
        if f.get("evidence"):
            out.append(f"  ```\n  {f['evidence']}\n  ```")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="React Native Android Play policy scanner")
    ap.add_argument("path", help="path to the RN/Expo project root")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    findings = []
    scan_patterns(root, findings)
    scan_manifests(root, findings)
    scan_build_config(root, findings)
    scan_bare_rn(root, findings)
    scan_toolchain(root, findings)
    scan_abi_and_signing(root, findings)
    scan_structural(root, findings)
    findings = dedupe(findings)

    if args.format == "json":
        print(json.dumps({"root": root, "platform": "android", "findings": findings}, indent=2))
    else:
        print(to_markdown(findings, root))
    return 0


if sys.version_info < (3, 8):
    raise SystemExit("scan.py requires Python 3.8+")


if __name__ == "__main__":
    sys.exit(main())
