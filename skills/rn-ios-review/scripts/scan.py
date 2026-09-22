#!/usr/bin/env python3
"""
Static App Store review scanner for React Native / Expo projects (iOS).

Grep-based lead generator for an App Store Review Guidelines audit.
Read-only: it never writes to the scanned project.

Usage:
    python3 scan.py /path/to/rn-project
    python3 scan.py /path/to/rn-project --format json > findings.json

Every hit needs human confirmation. A `sk_live_` string in a test fixture is
not a rejection, and the absence of a hit is not proof of compliance --- the
structural findings (moderation that exists on paper only, App Privacy answers
that contradict the SDK list, client-trusted entitlements) never show up in a grep.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {
    "node_modules", ".git", "build", "DerivedData", "Pods", ".expo",
    ".next", "dist", "coverage", "vendor", ".gradle", ".idea", "__pycache__",
    "android",  # iOS-only audit
}
CODE_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".json", ".plist", ".swift", ".m", ".mm",
    ".h", ".podspec", ".env", ".entitlements", ".xcprivacy", ".lock", ".pbxproj",
}
# Files whose "credentials" are public client identifiers by design. Firebase
# ships these to be committed; flagging them BLOCKER trained teams to ignore
# the whole category. Real secrets elsewhere are unaffected.
PUBLIC_CONFIG = re.compile(r"(GoogleService-Info\.plist|google-services\.json)$", re.I)

TEST_HINT = re.compile(
    r"(__tests__|__mocks__|\.test\.|\.spec\.|\.stories\.|/mocks?/|/fixtures?/|"
    r"[Ss]torybook/|e2e/|\.e2e\.)", re.I)

# id, severity, guideline, description, regex, extension filter (None = all)
RULES = [
    ("SECRET-HARDCODED", "BLOCKER", "1.6 / 2.5",
     "Possible hardcoded credential — the JS bundle ships in plaintext inside the IPA",
     re.compile(r"""(sk_live_|sk_test_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_\-]{30,}|"""
                r"""AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"""
                r"""(?i:(api[_-]?key|secret|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]))"""),
     None),

    ("DYNAMIC-CODE", "BLOCKER", "2.5.2",
     "Dynamic code execution — downloading or evaluating code is prohibited",
     re.compile(r"\beval\s*\(|new\s+Function\s*\(|Function\s*\(\s*['\"]return|vm\.runInNewContext"),
     None),

    ("EXTERNAL-PAYMENT", "BLOCKER", "3.1.1",
     "Possible external payment path for digital goods — confirm the SKU is a physical good or real-world service before clearing",
     re.compile(r"(?i)(openURL|Linking\.openURL|WebView[^\n]{0,80})[^\n]{0,120}"
                r"(stripe\.com|checkout\.stripe|paypal\.com|buy\.stripe|paddle\.com|lemonsqueezy|"
                r"/checkout|/upgrade|/subscribe|/billing)"),
     None),

    ("PAYMENT-SDK", "HIGH", "3.1.1",
     "Third-party payment SDK present — must not serve digital goods on iOS",
     re.compile(r"@stripe/stripe-react-native|react-native-paypal|react-native-braintree|"
                r"braintree-web-drop-in|react-native-razorpay|@paddle/paddle-js"),
     None),

    ("MINING", "BLOCKER", "2.5.18",
     "Possible on-device cryptocurrency mining",
     re.compile(r"(?i)(coinhive|cryptonight|minerd|stratum\+tcp|hashrate)"),
     None),

    ("PRIVATE-API", "BLOCKER", "2.5.1",
     "Possible private API usage in native code",
     re.compile(r"NSSelectorFromString\s*\(\s*@?\"_|valueForKey:\s*@\"_|performSelector:\s*NSSelectorFromString"),
     {".m", ".mm", ".h", ".swift"}),

    ("ARBITRARY-LOADS", "HIGH", "1.6",
     "App Transport Security disabled — cleartext traffic allowed",
     re.compile(r"NSAllowsArbitraryLoads</key>\s*<true/>|NSAllowsArbitraryLoads[\"']?\s*[:=]\s*true"),
     None),

    ("INSECURE-STORAGE", "HIGH", "1.6",
     "Token or personal data in AsyncStorage (unencrypted on disk) — use SecureStore / Keychain",
     re.compile(r"AsyncStorage\.setItem\s*\(\s*['\"][^'\"]*(token|auth|password|secret|session|patient|phi|ssn|dob|mrn|card)"),
     None),

    ("TRACKING-SDK", "HIGH", "5.1.2",
     "Tracking / analytics / ads SDK — needs ATT before it initializes, plus matching App Privacy answers",
     re.compile(r"react-native-fbsdk|@react-native-firebase/analytics|react-native-appsflyer|"
                r"react-native-adjust|react-native-branch|react-native-applovin-max|"
                r"react-native-google-mobile-ads|@amplitude/|mixpanel-react-native|"
                r"@segment/analytics|react-native-idfa|react-native-onesignal"),
     {".json", ".ts", ".tsx", ".js", ".jsx"}),

    ("CLIENT-ENTITLEMENT", "HIGH", "2.5.13",
     "Purchase entitlement possibly trusted from local storage — validate the receipt server-side",
     re.compile(r"(?i)(AsyncStorage|localStorage)[^\n]{0,60}(isPremium|isPro|['\"]pro['\"]|subscribed|entitle)"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("REVIEW-PROMPT", "MEDIUM", "5.6.1",
     "Possible custom rating prompt — only the system StoreReview API is allowed",
     re.compile(r"(?i)\b(rate\s+us\b|five\s+stars|5\s+stars|leave\s+(us\s+)?a\s+review|"
                r"rate\s+this\s+app|rate\s+the\s+app)"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("CROSS-PLATFORM-COPY", "LOW", "2.3.10",
     "Reference to another platform in user-facing copy",
     re.compile(r"(?i)['\"][^'\"]{0,60}(also available on (android|google play)|download on google play|"
                r"get it on (the )?play store|android (app|version))[^'\"]{0,60}['\"]"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("CONSOLE-LOG", "LOW", "Quality · PII leakage risk",
     "console logging in source — strip from release paths and check it never logs personal data",
     re.compile(r"\bconsole\.(log|debug|info)\s*\("),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("CRASH-PII", "HIGH", "5.1.1 / 5.1.2",
     "Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in App Privacy",
     re.compile(r"(?i)(Sentry\.(setContext|setUser|setExtra)|Bugsnag\.(setUser|addMetadata)|"
                r"crashlytics\(\)\.set|logEvent)\s*\([^)]{0,120}"
                r"\b(mrn|patient|dob|ssn|diagnos|email|phone|"
                r"(?:user|full|first|last|real|patient)_?name)\b"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("WEBVIEW-SHELL", "MEDIUM", "4.2",
     "WebView usage — if it is the primary surface, the app may be judged a repackaged website",
     re.compile(r"<WebView|from\s+['\"]react-native-webview['\"]"),
     {".ts", ".tsx", ".js", ".jsx"}),

    ("OTA-UPDATES", "MEDIUM", "2.3.1 / 2.5.2",
     "OTA update channel — permitted for fixes and content, not for shipping unreviewed features",
     re.compile(r"expo-updates|react-native-code-push|CodePush"),
     {".json", ".ts", ".tsx", ".js", ".jsx"}),
]

# Rules whose evidence spans more than one line (plist key/value pairs).
# scan_patterns is line-scoped, so these are matched against whole-file text.
MULTILINE_IDS = {"ARBITRARY-LOADS"}

BACKGROUND_MODES = re.compile(r"UIBackgroundModes")
PURPOSE_KEYS = re.compile(r"NS\w*UsageDescription")
VAGUE_PURPOSE = re.compile(
    r"(?i)^(this app|the app|we|app)?\s*(needs|requires|would like|uses|wants)?\s*"
    r"(access to )?(your )?(the )?(camera|photos|photo library|location|microphone|contacts|"
    r"bluetooth|calendar|reminders|health data|media)\.?\s*$"
)


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in CODE_EXT or fn in {"Info.plist", "Podfile", "Podfile.lock", ".env"}:
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
        text = "".join(lines)
        for rule_id, sev, guideline, desc, rx, exts in RULES:
            if exts and ext not in exts:
                continue
            if is_public_config and rule_id == "SECRET-HARDCODED":
                continue
            if rule_id in MULTILINE_IDS:
                m = rx.search(text)
                if m:
                    findings.append({
                        "id": rule_id,
                        "severity": "LOW" if is_test and sev in ("BLOCKER", "HIGH") else sev,
                        "guideline": guideline, "description": desc,
                        "file": rel,
                        "line": text[:m.start()].count("\n") + 1,
                        "evidence": m.group(0).replace("\n", " ").strip()[:180],
                    })
                continue
            for i, line in enumerate(lines, 1):
                if len(line) > 2000:
                    continue
                if rx.search(line):
                    findings.append({
                        "id": rule_id,
                        "severity": "LOW" if is_test and sev in ("BLOCKER", "HIGH") else sev,
                        "guideline": guideline,
                        "description": desc + (" [in a test/fixture path — verify]" if is_test else ""),
                        "file": rel,
                        "line": i,
                        "evidence": line.strip()[:180],
                    })


def scan_plists(root, findings):
    """Purpose strings and background modes in Info.plist and Expo config."""
    targets = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn == "Info.plist" or fn in {"app.json", "app.config.json"}:
                targets.append(os.path.join(dirpath, fn))
    for path in targets:
        rel = os.path.relpath(path, root)
        try:
            lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            if BACKGROUND_MODES.search(line):
                findings.append({
                    "id": "BACKGROUND-MODES", "severity": "MEDIUM", "guideline": "2.5.4",
                    "description": "Background modes declared — every entry must be genuinely used for its "
                                   "declared purpose, or it is a rejection",
                    "file": rel, "line": i + 1, "evidence": line.strip()[:180],
                })
            if not PURPOSE_KEYS.search(line):
                continue
            if rel.endswith(".json"):
                m = re.search(r':\s*"([^"]*)"', line)
                value = m.group(1) if m else ""
                lineno = i + 1
            else:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                m = re.search(r"<string>(.*?)</string>", nxt)
                value = m.group(1) if m else ""
                lineno = i + 2
            if not value.strip():
                sev, note = "HIGH", "Purpose string is empty"
            elif len(value) < 30 or VAGUE_PURPOSE.match(value.strip()):
                sev, note = "MEDIUM", "Purpose string is vague — state the specific feature and the user benefit"
            else:
                continue
            findings.append({
                "id": "PURPOSE-STRING", "severity": sev, "guideline": "5.1.1(ii)",
                "description": note, "file": rel, "line": lineno,
                "evidence": (line.strip() + " → " + value)[:180],
            })


def scan_bare_rn(root, findings):
    """Checks that only apply to bare RN (CLI) projects, where ios/ is checked in.

    Managed Expo generates these at prebuild, so they are absent from source and
    unverifiable; bare projects own them directly, which means they are both
    checkable and a common source of rejections.
    """
    ios_dir = os.path.join(root, "ios")
    if not os.path.isdir(ios_dir):
        return

    # --- Deployment target from the Podfile
    podfile = os.path.join(ios_dir, "Podfile")
    if os.path.isfile(podfile):
        text = open(podfile, encoding="utf-8", errors="ignore").read()
        m = re.search(r"^\s*platform\s+:ios\s*,\s*['\"]?([\d.]+)", text, re.M)
        if m:
            try:
                major = int(float(m.group(1)))
            except ValueError:
                major = None
            _report_deployment_target(findings, m.group(1), "ios/Podfile", m.group(0))

    # The Podfile on modern RN reads `platform :ios, min_ios_version_supported`,
    # which has no digits to parse. The authoritative value is in the pbxproj —
    # which bare RN checks in, and which nothing else here reads.
    lowest, where = None, None
    for dirpath, dirnames, filenames in os.walk(ios_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn != "project.pbxproj":
                continue
            path = os.path.join(dirpath, fn)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for pm in re.finditer(r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*([\d.]+)", text):
                try:
                    val = float(pm.group(1))
                except ValueError:
                    continue
                if lowest is None or val < lowest:
                    lowest, where = val, os.path.relpath(path, root)
    if lowest is not None:
        _report_deployment_target(findings, ("%g" % lowest), where,
                                  "IPHONEOS_DEPLOYMENT_TARGET = %g" % lowest)

    # --- Third-party pods: each needs its own privacy manifest
    lock = os.path.join(ios_dir, "Podfile.lock")
    if os.path.isfile(lock):
        text = open(lock, encoding="utf-8", errors="ignore").read()
        pods = set(re.findall(r"^  - ([A-Za-z0-9_+\-\.\/]+)\s", text, re.M))
        third_party = sorted(p for p in pods
                             if not p.startswith(("React", "RCT", "Yoga", "boost",
                                                  "DoubleConversion", "glog", "fmt",
                                                  "RNCAsyncStorage", "hermes")))
        if third_party:
            findings.append({
                "id": "POD-PRIVACY-MANIFESTS", "severity": "MEDIUM", "guideline": "Privacy manifests",
                "description": f"{len(third_party)} third-party pods in Podfile.lock. Any SDK on Apple's "
                               f"commonly-used list must ship its own PrivacyInfo.xcprivacy and a signature; "
                               f"a stale pod version that lacks one fails validation at upload. Check each "
                               f"against Apple's list and update the laggards — this is the most common "
                               f"bare-RN upload failure.",
                "file": "ios/Podfile.lock", "line": 0,
                "evidence": ", ".join(third_party[:8]) + ("..." if len(third_party) > 8 else ""),
            })

    # --- Entitlements need justification
    for dirpath, dirnames, filenames in os.walk(ios_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".entitlements"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            text = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
            flagged = [k for k in ("com.apple.developer.healthkit",
                                   "com.apple.developer.networking.vpn.api",
                                   "com.apple.developer.family-controls",
                                   "com.apple.developer.associated-domains",
                                   "com.apple.developer.icloud-container-identifiers")
                       if k in text]
            if flagged:
                findings.append({
                    "id": "ENTITLEMENTS-REVIEW", "severity": "MEDIUM", "guideline": "2.5.1 / 5.1.3 / 5.4",
                    "description": "Entitlements present that reviewers scrutinise: " +
                                   ", ".join(k.rsplit(".", 1)[-1] for k in flagged) +
                                   ". Each needs a matching feature and, for HealthKit and VPN, specific "
                                   "purpose strings and an approved use. An unused entitlement is a rejection.",
                    "file": rel, "line": 0, "evidence": ", ".join(flagged),
                })


def scan_upload_gates(root, findings):
    """Hard upload failures. These never reach a human reviewer — the build is
    rejected by App Store Connect — so they outrank every guideline finding.

    Deliberately reaches into Pods/ and node_modules/, which SKIP_DIRS excludes
    for every other pass: on bare RN that is exactly where the offending code
    lives, and a vendored UIWebView fails the upload just as hard as your own.
    """
    # UIWebView — ITMS-90809, an error (not a warning) since December 2020.
    hits, scanned = [], 0
    for sub in ("ios/Pods", "node_modules"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            if sub == "node_modules" and "/ios/" not in dirpath.replace(os.sep, "/") + "/":
                # only the iOS side of RN packages can contain UIKit code
                dirnames[:] = [d for d in dirnames if d in ("ios",) or not dirpath.endswith("node_modules")]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in {".m", ".mm", ".h", ".swift"}:
                    continue
                path = os.path.join(dirpath, fn)
                scanned += 1
                if scanned > 20000:
                    break
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if "UIWebView" in line:
                                hits.append((os.path.relpath(path, root), i, line.strip()[:180]))
                                break
                except OSError:
                    continue
    if hits:
        rel, line, evidence = hits[0]
        findings.append({
            "id": "UIWEBVIEW", "severity": "BLOCKER", "guideline": "2.5.1 / upload validation",
            "description": f"Deprecated UIWebView found in {len(hits)} vendored file(s). Apple rejects "
                           f"uploads containing UIWebView (ITMS-90809) — this build cannot be submitted "
                           f"at all. Usually means an old pod or an RN core below 0.60; the fix is "
                           f"upgrading the dependency, not editing vendored code.",
            "file": rel, "line": line, "evidence": evidence,
        })


def scan_privacy_manifest_contents(root, findings):
    """Presence was checked; contents never were. An empty
    NSPrivacyCollectedDataTypes on an app that transmits user data contradicts
    whatever App Privacy says, and the mismatch is itself the finding."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn != "PrivacyInfo.xcprivacy":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            try:
                text = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "NSPrivacyCollectedDataTypes" not in text:
                continue
            empty = re.search(r"<key>NSPrivacyCollectedDataTypes</key>\s*<array\s*/>", text)
            if not empty:
                continue
            findings.append({
                "id": "PRIVACY-MANIFEST-EMPTY", "severity": "HIGH", "guideline": "5.1.1 / 5.1.2",
                "description": "PrivacyInfo.xcprivacy declares NSPrivacyCollectedDataTypes as an empty "
                               "array. If the app sends anything to your own backend or to an analytics "
                               "SDK — account details, health metrics, user content — that is collection "
                               "and must be declared here and match the App Privacy answers. Apple treats "
                               "the mismatch between the two as the violation.",
                "file": rel, "line": text[:empty.start()].count("\n") + 1,
                "evidence": "<key>NSPrivacyCollectedDataTypes</key> <array/>",
            })


def scan_icon(root, findings):
    """CFBundleIconName must be present and non-empty on iOS 11+ SDK builds,
    or the upload fails with ITMS-90713."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn != "Info.plist":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            if TEST_HINT.search(rel):
                continue
            try:
                text = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "CFBundleIconName" not in text:
                continue
            m = re.search(r"<key>CFBundleIconName</key>\s*<string>(.*?)</string>", text, re.S)
            if m and not m.group(1).strip():
                findings.append({
                    "id": "ICON-NAME-MISSING", "severity": "BLOCKER",
                    "guideline": "upload validation",
                    "description": "CFBundleIconName is present but empty. The upload fails with "
                                   "ITMS-90713 — it must name an asset-catalog icon set that exists.",
                    "file": rel, "line": text[:m.start()].count("\n") + 1,
                    "evidence": "<key>CFBundleIconName</key> <string></string>",
                })


def _report_deployment_target(findings, value, rel, evidence):
    """Severity tracks buildability, not age: a target below 12 cannot be built
    by any currently shippable Xcode, which is a different problem from merely
    supporting old devices."""
    try:
        major = int(float(value))
    except ValueError:
        return
    if major >= 15:
        return
    if any(f["id"] == "DEPLOYMENT-TARGET-OLD" for f in findings):
        return
    blocking = major < 12
    findings.append({
        "id": "DEPLOYMENT-TARGET-OLD",
        "severity": "BLOCKER" if blocking else "MEDIUM",
        "guideline": "2.4.1",
        "description": f"iOS deployment target is {value}. "
                       + ("No currently shippable Xcode can build for this target — it has to be "
                          "raised before the project can be archived at all. "
                          if blocking else
                          "Old targets pull in deprecated pod versions that may lack privacy "
                          "manifests, and block newer APIs (Declared Age Range needs iOS 26). ")
                       + "Cross-check it against the floor your pods build at: if the app target is "
                         "lower, the App Store offers the app to devices where it will crash on "
                         "missing symbols.",
        "file": rel, "line": 0, "evidence": evidence,
    })


def scan_structural(root, findings):
    """Repo-wide presence/absence checks."""
    # Account creation without in-app deletion
    if _grep(root, r"(?i)(signUp|sign_up|createUser|createAccount|registerUser|auth/register)") \
            and not _grep(root, r"(?i)(deleteAccount|delete_account|account/delete|deleteUser|closeAccount)"):
        findings.append({
            "id": "ACCOUNT-DELETION", "severity": "HIGH", "guideline": "5.1.1(v)",
            "description": "Account creation found with no in-app deletion path. Deletion must be initiated "
                           "inside the app — linking out to a web form is not sufficient.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # An app that turns ad-identifier collection off is not "tracking" under
    # 5.1.2, so requiring an ATT prompt would be wrong. PlinkHealth does exactly
    # this: AdSupport unlinked, ad personalisation and ad user data both false.
    ad_tracking_disabled = _grep(
        root, r"analytics_default_allow_ad_personalization_signals[\"']?\s*:\s*false|"
              r"analytics_default_allow_ad_user_data[\"']?\s*:\s*false|"
              r"google_analytics_adid_collection_enabled[\"']?\s*(?::|=|android:value=)\s*[\"']?false") \
        or _grep(root, r"<key>NSPrivacyTracking</key>\s*<false/>")

    # Tracking SDKs without ATT
    if not ad_tracking_disabled and \
            _grep(root, r"@react-native-firebase/analytics|react-native-fbsdk|react-native-appsflyer|"
                   r"react-native-adjust|react-native-applovin-max|"
                   r"react-native-google-mobile-ads|@amplitude/|mixpanel-react-native") \
            and not _grep(root, r"requestTrackingPermissionsAsync|getTrackingPermissionsAsync|"
                                r"requestTrackingPermission|AppTrackingTransparency"):
        findings.append({
            "id": "ATT-MISSING", "severity": "HIGH", "guideline": "5.1.2",
            "description": "Tracking / ads / analytics SDK present with no App Tracking Transparency request. "
                           "ATT must resolve before the SDK initializes, and NSUserTrackingUsageDescription must be set.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # ATT present but no usage description
    if _grep(root, r"requestTrackingPermissionsAsync|AppTrackingTransparency") \
            and not _grep(root, r"NSUserTrackingUsageDescription"):
        findings.append({
            "id": "ATT-STRING-MISSING", "severity": "HIGH", "guideline": "5.1.2",
            "description": "ATT is requested but NSUserTrackingUsageDescription was not found — the prompt will "
                           "not display and the app will be rejected.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # Privacy manifest — managed Expo has no ios/ dir; the manifest appears at prebuild
    if not _exists(root, "PrivacyInfo.xcprivacy"):
        managed = not os.path.isdir(os.path.join(root, "ios"))
        if managed:
            findings.append({
                "id": "PRIVACY-MANIFEST-UNVERIFIED", "severity": "MEDIUM", "guideline": "Privacy manifests",
                "description": "No ios/ directory, so this looks like a managed Expo project and the privacy manifest "
                               "could not be checked from source. Run `expo prebuild` and confirm the app target has a "
                               "PrivacyInfo.xcprivacy declaring collected data types and approved reasons for "
                               "required-reason APIs.",
                "file": "(managed Expo)", "line": 0, "evidence": "",
            })
        else:
            findings.append({
                "id": "PRIVACY-MANIFEST", "severity": "HIGH", "guideline": "Privacy manifests",
                "description": "No PrivacyInfo.xcprivacy found in the ios/ directory. The app target needs one declaring "
                               "collected data types, tracking domains, and approved reasons for required-reason APIs; "
                               "third-party SDKs need their own.",
                "file": "ios/", "line": 0, "evidence": "",
            })

    # IAP without restore
    if _grep(root, r"react-native-iap|react-native-purchases|expo-in-app-purchases") \
            and not _grep(root, r"(?i)(restorePurchases|restoreCompletedTransactions|getAvailablePurchases|restore)"):
        findings.append({
            "id": "RESTORE-MISSING", "severity": "HIGH", "guideline": "3.1.1",
            "description": "IAP integration found with no restore-purchases path. Non-consumables and subscriptions "
                           "need a visible Restore Purchases control.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # UGC without moderation
    if _grep(root, r"(?i)(createPost|newComment|sendMessage|uploadPhoto|publishPost|<Feed|postComment)") \
            and not _grep(root, r"(?i)(reportContent|reportPost|reportUser|blockUser|muteUser|flagContent|moderat)"):
        findings.append({
            "id": "UGC-MODERATION", "severity": "HIGH", "guideline": "1.2",
            "description": "User-generated content features found with no report/block/moderation path. Apple requires "
                           "content filtering, in-app reporting, user blocking, and published contact information.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # Privacy policy
    if not _grep(root, r"(?i)(privacy[- _]?policy|privacyPolicyUrl)"):
        findings.append({
            "id": "PRIVACY-POLICY", "severity": "BLOCKER", "guideline": "5.1.1(i)",
            "description": "No privacy policy reference found in the app. A policy must be linked in App Store Connect "
                           "and reachable inside the app.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })

    # Social login without a compliant alternative
    if _grep(root, r"(?i)(GoogleSignin|react-native-fbsdk|LoginManager|signInWithFacebook|signInWithGoogle)") \
            and not _grep(root, r"(?i)(AppleAuthentication|apple-authentication|signInWithApple|AppleButton)"):
        findings.append({
            "id": "LOGIN-ALTERNATIVE", "severity": "MEDIUM", "guideline": "4.8",
            "description": "Third-party social login found with no privacy-preserving alternative. Offer a login that "
                           "limits data to name and email and allows a private email — Sign in with Apple is simplest.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })


def _exists(root, name):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if name in filenames:
            return True
    return False


_grep_cache = {}


def _grep(root, pattern):
    """Cheap repo-wide existence check, ignoring test/fixture paths."""
    key = (root, pattern)
    if key in _grep_cache:
        return _grep_cache[key]
    rx = re.compile(pattern)
    hit = False
    for path in iter_files(root):
        if os.path.splitext(path)[1].lower() not in {".ts", ".tsx", ".js", ".jsx", ".json", ".plist"}:
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
                "id": rule_id, "severity": "INFO", "guideline": "",
                "description": f"...and {count - cap} more occurrences of {rule_id}",
                "file": "", "line": 0, "evidence": "",
            })
    return out


ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def to_markdown(findings, root):
    counts = defaultdict(int)
    for f in findings:
        counts[f["severity"]] += 1
    out = [f"# App Store review scan — `{root}`", "", "| Severity | Count |", "|---|---|"]
    for sev in ["BLOCKER", "HIGH", "MEDIUM", "LOW"]:
        out.append(f"| {sev} | {counts[sev]} |")
    out += ["", "_Grep-based leads only. Confirm every hit; structural issues (moderation quality, "
                "App Privacy accuracy, server-side receipt validation) are not detectable here._", ""]
    findings.sort(key=lambda f: (ORDER.get(f["severity"], 5), f["id"], f.get("file", "")))
    current = None
    for f in findings:
        if f["severity"] != current:
            current = f["severity"]
            out.append(f"\n## {current}\n")
        loc = f"`{f['file']}:{f['line']}`" if f.get("file") and f.get("line") else (f"`{f['file']}`" if f.get("file") else "")
        out.append(f"- **{f['id']}** {loc} — {f['description']}"
                   + (f"  \n  _Guideline {f['guideline']}_" if f["guideline"] else ""))
        if f.get("evidence"):
            out.append(f"  ```\n  {f['evidence']}\n  ```")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="React Native iOS App Store review scanner")
    ap.add_argument("path", help="path to the RN/Expo project root")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    findings = []
    scan_patterns(root, findings)
    scan_plists(root, findings)
    scan_bare_rn(root, findings)
    scan_upload_gates(root, findings)
    scan_icon(root, findings)
    scan_privacy_manifest_contents(root, findings)
    scan_structural(root, findings)
    findings = dedupe(findings)

    if args.format == "json":
        print(json.dumps({"root": root, "platform": "ios", "findings": findings}, indent=2))
    else:
        print(to_markdown(findings, root))
    return 0


if sys.version_info < (3, 8):
    raise SystemExit("scan.py requires Python 3.8+")


if __name__ == "__main__":
    sys.exit(main())
