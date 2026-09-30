#!/usr/bin/env python3
"""
Tests for both store scanners.

Two fixture projects:
  - "dirty": deliberately violates rules; asserts each expected finding fires.
  - "clean": a plausible compliant RN app; asserts the BLOCKER/HIGH rules stay
    quiet. This is the false-positive guard, and it is the more important half —
    a scanner that flags everything is worse than no scanner, because people
    stop reading it.

Run:  python3 tests/test_scanners.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IOS_SCAN = os.path.join(ROOT, "skills", "rn-ios-review", "scripts", "scan.py")
ANDROID_SCAN = os.path.join(ROOT, "skills", "rn-android-review", "scripts", "scan.py")


def write(base, rel, content):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def run_scan(script, project):
    out = subprocess.run(
        [sys.executable, script, project, "--format", "json"],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise AssertionError(f"scanner failed: {out.stderr}")
    return json.loads(out.stdout)


def ids(result):
    return {f["id"] for f in result["findings"]}


def sev(result, finding_id):
    for f in result["findings"]:
        if f["id"] == finding_id:
            return f["severity"]
    return None


def make_dirty(base):
    write(base, "package.json", json.dumps({
        "name": "dirty", "dependencies": {
            "react-native": "0.74.0", "react-native-iap": "12.0.0",
            "@react-native-firebase/analytics": "18.0.0",
            "@react-native-google-signin/google-signin": "10.0.0",
            "react-native-webview": "13.0.0",
        }}))
    write(base, "src/Paywall.tsx", """
import { Linking } from 'react-native';
const API_KEY = "sk_live_abcdefghijklmnop12345";
export function upgrade() { Linking.openURL('https://buy.stripe.com/checkout'); }
export function signUp() { return api.post('/auth/register'); }
export async function isPro() { return AsyncStorage.getItem('isPremium'); }
console.log('paywall debug');
""")
    write(base, "src/Feed.tsx", """
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { WebView } from 'react-native-webview';
export function createPost(body) { return api.post('/posts', body); }
""")
    write(base, "ios/App/Info.plist", """<plist><dict>
<key>NSCameraUsageDescription</key>
<string>This app needs camera access</string>
<key>UIBackgroundModes</key>
<array><string>location</string></array>
</dict></plist>""")
    write(base, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
  <uses-permission android:name="android.permission.QUERY_ALL_PACKAGES"/>
  <application android:usesCleartextTraffic="true" android:allowBackup="true"/>
</manifest>""")
    write(base, "android/app/build.gradle",
          "android { defaultConfig { targetSdkVersion 34 } }\n"
          "dependencies { implementation 'com.android.billingclient:billing:6.1.0' }")
    write(base, ".github/workflows/release.yml", "run: cd android && ./gradlew assembleRelease")


def make_clean(base):
    """A plausible compliant app. Nothing here should trip a BLOCKER or HIGH."""
    write(base, "package.json", json.dumps({
        "name": "clean", "dependencies": {
            "react-native": "0.76.0",
            "react-native-purchases": "8.0.0",
            "expo-secure-store": "13.0.0",
            "expo-tracking-transparency": "5.0.0",
            "expo-apple-authentication": "7.0.0",
        }}))
    write(base, "src/Paywall.tsx", """
import Purchases from 'react-native-purchases';
import * as SecureStore from 'expo-secure-store';
export async function buy(pkg) { return Purchases.purchasePackage(pkg); }
export async function restore() { return Purchases.restorePurchases(); }
export async function saveToken(t) { return SecureStore.setItemAsync('authToken', t); }
export const PRIVACY_POLICY_URL = 'https://example.com/privacy-policy';
""")
    write(base, "src/Account.tsx", """
export function signUp(email) { return api.post('/auth/register', { email }); }
export function deleteAccount() { return api.delete('/account'); }
""")
    write(base, "src/Social.tsx", """
import { requestTrackingPermissionsAsync } from 'expo-tracking-transparency';
export async function initTracking() { return requestTrackingPermissionsAsync(); }
export function createPost(b) { return api.post('/posts', b); }
export function reportContent(id, reason) { return api.post('/reports', { id, reason }); }
export function blockUser(id) { return api.post('/blocks', { id }); }
""")
    write(base, "ios/App/Info.plist", """<plist><dict>
<key>NSCameraUsageDescription</key>
<string>Take a photo of your insurance card so we can attach it to your claim.</string>
<key>NSUserTrackingUsageDescription</key>
<string>Allows us to measure which referral partners send patients who complete onboarding.</string>
</dict></plist>""")
    write(base, "ios/App/PrivacyInfo.xcprivacy", "<plist><dict/></plist>")
    write(base, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.INTERNET"/>
  <application android:allowBackup="false"/>
</manifest>""")
    write(base, "android/app/build.gradle",
          "android { defaultConfig { targetSdkVersion 36 } }\n"
          "dependencies { implementation 'com.android.billingclient:billing:8.0.0' }")
    write(base, "src/Billing.ts",
          "export async function verify(purchaseToken) { return api.post('/verify', { purchaseToken }); }")
    write(base, ".github/workflows/release.yml", "run: cd android && ./gradlew bundleRelease")


class ScannerTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.dirty = os.path.join(cls.tmp, "dirty")
        cls.clean = os.path.join(cls.tmp, "clean")
        make_dirty(cls.dirty)
        make_clean(cls.clean)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestIOSScanner(ScannerTestBase):
    def test_detects_violations(self):
        found = ids(run_scan(IOS_SCAN, self.dirty))
        for expected in [
            "SECRET-HARDCODED", "EXTERNAL-PAYMENT", "PRIVACY-POLICY",
            "ACCOUNT-DELETION", "ATT-MISSING", "PRIVACY-MANIFEST",
            "RESTORE-MISSING", "UGC-MODERATION", "CLIENT-ENTITLEMENT",
            "PURPOSE-STRING", "LOGIN-ALTERNATIVE", "BACKGROUND-MODES",
        ]:
            self.assertIn(expected, found, f"iOS scanner missed {expected}")

    def test_no_false_positives_on_clean(self):
        result = run_scan(IOS_SCAN, self.clean)
        noisy = [f for f in result["findings"] if f["severity"] in ("BLOCKER", "HIGH")]
        self.assertEqual(noisy, [], f"false positives on clean project: {[f['id'] for f in noisy]}")

    def test_skips_android_dir(self):
        for f in run_scan(IOS_SCAN, self.dirty)["findings"]:
            self.assertNotIn("android/", f.get("file", ""))

    def test_test_fixtures_downgraded(self):
        """A secret in a __tests__ path should not be a BLOCKER."""
        proj = os.path.join(self.tmp, "fixtured")
        write(proj, "package.json", '{"name":"f"}')
        write(proj, "src/__tests__/auth.test.ts", 'const API_KEY = "sk_live_abcdefghijklmnop12345";')
        self.assertEqual(sev(run_scan(IOS_SCAN, proj), "SECRET-HARDCODED"), "LOW")

    def test_specific_purpose_string_passes(self):
        for f in run_scan(IOS_SCAN, self.clean)["findings"]:
            self.assertNotEqual(f["id"], "PURPOSE-STRING",
                                "specific purpose string wrongly flagged as vague")


class TestAndroidScanner(ScannerTestBase):
    def test_detects_violations(self):
        found = ids(run_scan(ANDROID_SCAN, self.dirty))
        for expected in [
            "TARGET-SDK", "BILLING-VERSION", "APK-NOT-AAB", "SECRET-HARDCODED",
            "EXTERNAL-PAYMENT", "PRIVACY-POLICY", "ACCOUNT-DELETION",
            "UGC-MODERATION", "CLEARTEXT", "ALLOW-BACKUP",
            "PERM-ACCESS_BACKGROUND_LOCATION", "PERM-QUERY_ALL_PACKAGES",
        ]:
            self.assertIn(expected, found, f"Android scanner missed {expected}")

    def test_no_false_positives_on_clean(self):
        result = run_scan(ANDROID_SCAN, self.clean)
        noisy = [f for f in result["findings"] if f["severity"] in ("BLOCKER", "HIGH")]
        self.assertEqual(noisy, [], f"false positives on clean project: {[f['id'] for f in noisy]}")

    def test_target_sdk_at_floor_passes(self):
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.clean), "TARGET-SDK"))

    def test_warns_when_merged_manifest_absent(self):
        self.assertIn("MERGED-MANIFEST-NOT-CHECKED", ids(run_scan(ANDROID_SCAN, self.dirty)),
                      "scanner must disclose that it only read the source manifest")

    def test_skips_ios_dir(self):
        for f in run_scan(ANDROID_SCAN, self.dirty)["findings"]:
            self.assertNotIn("ios/", f.get("file", ""))


class TestRealWorldFalsePositives(ScannerTestBase):
    """Regression tests for false positives found by running against a real
    production RN app (bluesky-social/social-app). Each of these fired as a
    BLOCKER or HIGH on compliant code before being fixed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fp = os.path.join(cls.tmp, "falsepos")
        write(cls.fp, "package.json", json.dumps({
            "name": "fp", "dependencies": {
                "@braintree/sanitize-url": "^6.0.2",   # URL sanitizer, NOT a payment SDK
                "react-native": "0.76.0",
            }}))
        write(cls.fp, "src/Link.tsx",
              "import {sanitizeUrl} from '@braintree/sanitize-url'\nexport const Link = () => null")
        write(cls.fp, "src/telemetry.ts",
              "// publish is a separate user action that runs later\n"
              "// we adjust the offset here, then adjust the pref\n")
        write(cls.fp, "src/view/Storybook/Forms.tsx", "console.log('storybook only')")
        write(cls.fp, "src/Account.tsx",
              "export function signUp(e) { return api.post('/register', e) }\n"
              "export function deleteAccount() { return api.delete('/account') }\n"
              "export const PRIVACY_POLICY_URL = 'https://x.test/privacy-policy'")

    def test_braintree_url_sanitizer_is_not_a_payment_sdk(self):
        for scan in (IOS_SCAN, ANDROID_SCAN):
            self.assertIsNone(sev(run_scan(scan, self.fp), "PAYMENT-SDK"),
                              "@braintree/sanitize-url wrongly flagged as a payment SDK")

    def test_word_adjust_is_not_an_analytics_sdk(self):
        """'we adjust the offset' must not match the react-native-adjust SDK."""
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.fp), "ATT-MISSING"),
                          "the English word 'adjust' wrongly matched a tracking SDK")

    def test_separate_user_is_not_a_rating_prompt(self):
        """'sepaRATE USer' must not match 'rate us'."""
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.fp), "REVIEW-PROMPT"),
                          "'separate user' wrongly matched a custom rating prompt")

    def test_storybook_console_log_downgraded(self):
        result = run_scan(IOS_SCAN, self.fp)
        self.assertIn(sev(result, "CONSOLE-LOG"), (None, "LOW"))

    def test_managed_expo_privacy_manifest_is_not_high(self):
        """No ios/ dir means managed Expo — the manifest appears at prebuild."""
        result = run_scan(IOS_SCAN, self.fp)
        self.assertIsNone(sev(result, "PRIVACY-MANIFEST"),
                          "managed Expo project wrongly flagged for a missing privacy manifest")
        self.assertEqual(sev(result, "PRIVACY-MANIFEST-UNVERIFIED"), "MEDIUM")

    def test_noisy_rules_report_once(self):
        """OTA/WebView/tracking imports appear many times; report one finding."""
        proj = os.path.join(self.tmp, "repeats")
        write(proj, "package.json", '{"name":"r","dependencies":{"expo-updates":"1.0.0"}}')
        for i in range(6):
            write(proj, f"src/f{i}.ts", "import * as Updates from 'expo-updates'")
        findings = run_scan(IOS_SCAN, proj)["findings"]
        hits = [f for f in findings
                if f["id"] == "OTA-UPDATES" and f["severity"] != "INFO"]
        self.assertEqual(len(hits), 1, f"OTA-UPDATES reported {len(hits)} times, expected 1")
        # the roll-up line is expected, and should say how many were suppressed
        rollup = [f for f in findings if f["id"] == "OTA-UPDATES" and f["severity"] == "INFO"]
        self.assertEqual(len(rollup), 1)
        self.assertIn("more occurrences", rollup[0]["description"])


class TestBareRNProjects(ScannerTestBase):
    """Bare RN (CLI) projects check ios/ and android/ into the repo, so there is
    more to verify than in managed Expo — pods, entitlements, NDK, signing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bare = os.path.join(cls.tmp, "bare")
        write(cls.bare, "package.json",
              '{"name":"bare","dependencies":{"react-native":"0.73.0","react-native-iap":"12.0.0"}}')
        write(cls.bare, "ios/Podfile", "platform :ios, '13.4'\ntarget 'MyApp' do\nend")
        write(cls.bare, "ios/Podfile.lock",
              "PODS:\n  - React-Core (0.73.0)\n  - RNFBAnalytics (18.0.0)\n  - Sentry (8.20.0)\n")
        write(cls.bare, "ios/MyApp/MyApp.entitlements",
              "<plist><dict><key>com.apple.developer.healthkit</key><true/></dict></plist>")
        write(cls.bare, "android/build.gradle",
              'buildscript { ext { ndkVersion = "25.1.8937393"; targetSdkVersion = 36 } }')
        write(cls.bare, "android/gradle.properties",
              "MYAPP_RELEASE_STORE_PASSWORD=hunter2secret\nMYAPP_RELEASE_KEY_PASSWORD=hunter2secret")

    def test_old_deployment_target_flagged(self):
        self.assertEqual(sev(run_scan(IOS_SCAN, self.bare), "DEPLOYMENT-TARGET-OLD"), "MEDIUM")

    def test_pods_listed_for_privacy_manifest_review(self):
        self.assertEqual(sev(run_scan(IOS_SCAN, self.bare), "POD-PRIVACY-MANIFESTS"), "MEDIUM")

    def test_entitlements_flagged_for_review(self):
        self.assertEqual(sev(run_scan(IOS_SCAN, self.bare), "ENTITLEMENTS-REVIEW"), "MEDIUM")

    def test_privacy_manifest_is_high_when_ios_dir_exists(self):
        """Bare RN owns ios/, so a missing manifest is a real HIGH — not the
        managed-Expo 'unverified' downgrade."""
        result = run_scan(IOS_SCAN, self.bare)
        self.assertEqual(sev(result, "PRIVACY-MANIFEST"), "HIGH")
        self.assertIsNone(sev(result, "PRIVACY-MANIFEST-UNVERIFIED"))

    def test_old_ndk_flagged_for_16kb(self):
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.bare), "NDK-VERSION"), "HIGH")

    def test_signing_secret_in_gradle_properties(self):
        """UPPER_SNAKE is the RN CLI template convention — must still match."""
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.bare), "SIGNING-SECRET-COMMITTED"), "HIGH")

    def test_secret_value_is_redacted_in_output(self):
        for f in run_scan(ANDROID_SCAN, self.bare)["findings"]:
            self.assertNotIn("hunter2secret", json.dumps(f),
                             "scanner leaked a credential into its own output")

    def test_env_var_signing_config_not_flagged(self):
        clean = os.path.join(self.tmp, "signed_clean")
        write(clean, "package.json", '{"name":"c"}')
        write(clean, "android/build.gradle", "ext { ndkVersion = \"27.1.1\" }")
        write(clean, "android/gradle.properties",
              "MYAPP_RELEASE_STORE_PASSWORD=$System.getenv('KEYSTORE_PASSWORD')")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, clean), "SIGNING-SECRET-COMMITTED"))

    def test_bare_checks_silent_on_managed_expo(self):
        for check in ("DEPLOYMENT-TARGET-OLD", "POD-PRIVACY-MANIFESTS", "ENTITLEMENTS-REVIEW"):
            self.assertIsNone(sev(run_scan(IOS_SCAN, self.clean), check))


class TestOutputContract(ScannerTestBase):
    def test_json_shape(self):
        for script, platform in ((IOS_SCAN, "ios"), (ANDROID_SCAN, "android")):
            result = run_scan(script, self.dirty)
            self.assertEqual(result["platform"], platform)
            for f in result["findings"]:
                for key in ("id", "severity", "description", "file", "line"):
                    self.assertIn(key, f, f"{platform} finding missing {key}: {f}")
                self.assertIn(f["severity"],
                              ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"))

    def test_markdown_renders(self):
        for script in (IOS_SCAN, ANDROID_SCAN):
            out = subprocess.run([sys.executable, script, self.dirty],
                                 capture_output=True, text=True, timeout=120)
            self.assertEqual(out.returncode, 0)
            self.assertIn("| Severity | Count |", out.stdout)

    def test_missing_path_exits_nonzero(self):
        out = subprocess.run([sys.executable, IOS_SCAN, "/nope/nowhere"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)

    def test_empty_project_does_not_crash(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty, exist_ok=True)
        for script in (IOS_SCAN, ANDROID_SCAN):
            run_scan(script, empty)


# --------------------------------------------------------------------------
# Regression tests for gaps found auditing real bare-RN CLI projects.
# Each test names the real project that exposed the bug.
# --------------------------------------------------------------------------

class TestBareRNCorrectnessBugs(ScannerTestBase):
    """Checks that existed but were silently dead or wrong on bare RN."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)

    def test_ats_arbitrary_loads_detected_across_plist_lines(self):
        """an RN 0.49 project: plists put <key> and <true/> on separate lines, so the
        line-scoped regex never matched and a HIGH 1.6 check was dead."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.72.0"}}')
        write(self.proj, "ios/App/Info.plist", """<plist><dict>
<key>NSAppTransportSecurity</key>
<dict>
	<key>NSAllowsArbitraryLoads</key>
	<true/>
</dict>
</dict></plist>""")
        self.assertIn("ARBITRARY-LOADS", ids(run_scan(IOS_SCAN, self.proj)))

    def test_groovy_dsl_signing_password_detected(self):
        """three real projects all use space-separated Groovy DSL;
        the regex required '=' or ':' so it missed every real one."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.72.0"}}')
        write(self.proj, "android/app/build.gradle", """
android {
  signingConfigs {
    release {
      storeFile file('release.keystore')
      storePassword 'hunter2hunter2'
      keyAlias 'upload'
      keyPassword 'hunter2hunter2'
    }
  }
}
""")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SIGNING-SECRET-COMMITTED"), "HIGH")

    def test_android_fastlane_apk_build_detected(self):
        """two real projects keep Fastfile at android/fastlane/, which was
        not in the CI path list, so the APK-NOT-AAB BLOCKER fired on nothing."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.72.0"}}')
        write(self.proj, "android/fastlane/Fastfile", """
platform :android do
  lane :release do
    gradle(task: "assemble", build_type: "Release")
  end
end
""")
        self.assertIn("APK-NOT-AAB", ids(run_scan(ANDROID_SCAN, self.proj)))

    def test_target_sdk_below_discoverability_floor_is_worse(self):
        """Both branches assigned BLOCKER, collapsing the distinction the rule
        file spends a paragraph explaining."""
        old, near = os.path.join(self.tmp, "sdk22"), os.path.join(self.tmp, "sdk35")
        for base, target in ((old, 22), (near, 35)):
            write(base, "package.json", '{"dependencies":{"react-native":"0.72.0"}}')
            write(base, "android/app/build.gradle",
                  "android { defaultConfig { targetSdkVersion %d } }" % target)
        self.assertEqual(sev(run_scan(ANDROID_SCAN, old), "TARGET-SDK"), "BLOCKER")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, near), "TARGET-SDK"), "HIGH")


class TestRealWorldFalsePositives2(ScannerTestBase):
    """False positives that fired on every project in the fleet."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.72.0"}}')

    def test_firebase_ios_plist_is_not_a_hardcoded_secret(self):
        """47 projects ship GoogleService-Info.plist. The AIza key in it is a
        public client identifier, not a credential."""
        write(self.proj, "ios/App/GoogleService-Info.plist", """<plist><dict>
<key>API_KEY</key>
<string>AIzaSyC1234567890abcdefghijklmnopqrstuv</string>
</dict></plist>""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SECRET-HARDCODED"))

    def test_firebase_android_json_is_not_a_hardcoded_secret(self):
        write(self.proj, "android/app/google-services.json",
              '{"client":[{"api_key":[{"current_key":"AIzaSyC1234567890abcdefghijklmnopqrstuv"}]}]}')
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "SECRET-HARDCODED"))

    def test_real_secret_still_caught_outside_firebase_config(self):
        """Guard: the allowlist must not blind the rule everywhere else."""
        write(self.proj, "src/config.js",
              'export const cfg = { awsKey: "AKIAIOSFODNN7EXAMPLE" };')
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SECRET-HARDCODED"), "BLOCKER")

    def test_cleartext_in_debug_manifest_is_not_high(self):
        """20 projects carry this from the RN template; debug never ships."""
        write(self.proj, "android/app/src/debug/AndroidManifest.xml",
              '<manifest><application android:usesCleartextTraffic="true"/></manifest>')
        self.assertNotIn(sev(run_scan(ANDROID_SCAN, self.proj), "CLEARTEXT"),
                         ("BLOCKER", "HIGH"))

    def test_cleartext_in_main_manifest_is_still_high(self):
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><application android:usesCleartextTraffic="true"/></manifest>')
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj), "CLEARTEXT"), "HIGH")

    def test_analytics_event_with_no_pii_is_not_flagged(self):
        """a modern RN health app: every CRASH-PII hit was a bare event name or a count."""
        write(self.proj, "src/analytics.ts", """
export function track() {
  logEvent({ name: 'onboarding_finished' });
  logEvent({ name: 'sign_in', params: { method: 'biometric' } });
}
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "CRASH-PII"))


    def test_analytics_event_with_no_pii_is_not_flagged_android(self):
        """Same a modern RN health app false positive, Android scanner."""
        write(self.proj, "src/analytics.ts",
              "logEvent({ name: 'onboarding_finished' });")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "CRASH-PII"))

    def test_real_pii_in_analytics_still_flagged(self):
        """Guard: the narrowed regex must still catch actual PII."""
        write(self.proj, "src/bad.ts",
              "logEvent({ name: 'signup', params: { email: user.email } });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "CRASH-PII"), "HIGH")

    def test_att_not_required_when_ad_id_collection_disabled(self):
        """a modern RN health app deliberately does not link AdSupport and disables ad-id
        collection, so no ATT prompt is required."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.84.0",'
              '"@react-native-firebase/analytics":"23.0.0"}}')
        write(self.proj, "firebase.json", json.dumps({"react-native": {
            "analytics_default_allow_ad_personalization_signals": False,
            "analytics_default_allow_ad_user_data": False}}))
        write(self.proj, "ios/App/PrivacyInfo.xcprivacy",
              "<plist><dict><key>NSPrivacyTracking</key><false/></dict></plist>")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "ATT-MISSING"))

    def test_att_still_required_when_tracking_sdk_unconstrained(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.84.0","react-native-appsflyer":"6.0.0"}}')
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "ATT-MISSING"), "HIGH")


class TestMissingUploadGates(ScannerTestBase):
    """Hard upload failures the scanner could not produce at all."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.49.0"}}')

    def test_uiwebview_in_vendored_pods_is_blocker(self):
        """an RN 0.49 project: UIWebView in FBSDK pods = ITMS-90809, rejected since
        Dec 2020. Pods/ is in SKIP_DIRS so it was invisible."""
        write(self.proj, "ios/Pods/FBSDKCoreKit/FBSDKWebDialogView.m",
              "@interface FBSDKWebDialogView : UIView <UIWebViewDelegate>\n@end")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "UIWEBVIEW"), "BLOCKER")

    def test_empty_cfbundleiconname_is_blocker(self):
        """an RN 0.72 project ships this today: ITMS-90713."""
        write(self.proj, "ios/App/Info.plist", """<plist><dict>
<key>CFBundleIcons</key>
<dict>
	<key>CFBundlePrimaryIcon</key>
	<dict>
		<key>CFBundleIconName</key>
		<string></string>
	</dict>
</dict>
</dict></plist>""")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "ICON-NAME-MISSING"), "BLOCKER")

    def test_missing_arm64_abi_is_blocker(self):
        """an RN 0.49 project is armeabi-v7a + x86 only. Play has required 64-bit
        since Aug 2019 and rejects the upload outright."""
        write(self.proj, "android/app/build.gradle",
              'android { defaultConfig { targetSdkVersion 36\n'
              '  ndk { abiFilters "armeabi-v7a", "x86" } } }')
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj), "ABI-NO-64BIT"), "BLOCKER")

    def test_arm64_present_is_not_flagged(self):
        write(self.proj, "android/gradle.properties",
              "reactNativeArchitectures=armeabi-v7a,arm64-v8a,x86,x86_64")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "ABI-NO-64BIT"))

    def test_tracked_release_keystore_is_high(self):
        """an RN 0.72 project and an RN 0.49 project both commit one. Password + keystore in the
        repo means anyone with clone access can sign as you."""
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        write(self.proj, "android/keystores/release.keystore", "not-a-real-keystore")
        subprocess.run(["git", "add", "-A"], cwd=self.proj, check=True)
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "KEYSTORE-COMMITTED"), "HIGH")


class TestBatch2Gaps(ScannerTestBase):
    """Second batch: the pbxproj, the merged manifest, privacy-manifest
    contents, and the build toolchain — all previously unread."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def test_deployment_target_read_from_pbxproj_not_podfile(self):
        """an RN 0.76 project: Podfile says `platform :ios, min_ios_version_supported`,
        which has no digits, so the regex silently parsed nothing. The real
        value lives in the pbxproj."""
        write(self.proj, "ios/Podfile", "platform :ios, min_ios_version_supported\n")
        write(self.proj, "ios/App.xcodeproj/project.pbxproj",
              "buildSettings = {\n\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 12.4;\n};")
        self.assertIsNotNone(sev(run_scan(IOS_SCAN, self.proj), "DEPLOYMENT-TARGET-OLD"))

    def test_commented_podfile_platform_is_ignored(self):
        """an RN 0.49 project's Podfile has `# platform :ios, '9.0'` commented out; the
        regex matched the comment and reported it as the real target."""
        write(self.proj, "ios/Podfile", "# platform :ios, '9.0'\nplatform :ios, min_ios_version_supported\n")
        write(self.proj, "ios/App.xcodeproj/project.pbxproj",
              "buildSettings = {\n\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 8.0;\n};")
        result = run_scan(IOS_SCAN, self.proj)
        hit = [f for f in result["findings"] if f["id"] == "DEPLOYMENT-TARGET-OLD"]
        self.assertTrue(hit, "expected a deployment target finding")
        self.assertIn("pbxproj", hit[0]["file"],
                      "should cite the pbxproj, not a commented Podfile line")

    def test_ancient_deployment_target_is_blocker_not_medium(self):
        """an RN 0.49 project ships 8.0. No currently shippable Xcode can build that,
        so it is not the same finding as 12.4."""
        write(self.proj, "ios/App.xcodeproj/project.pbxproj",
              "buildSettings = {\n\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 8.0;\n};")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "DEPLOYMENT-TARGET-OLD"), "BLOCKER")

    def test_privacy_manifest_with_empty_collected_types_is_flagged(self):
        """a modern RN health app declares an empty NSPrivacyCollectedDataTypes while
        POSTing health records to its backend. Presence was checked; contents
        never were."""
        write(self.proj, "ios/App/PrivacyInfo.xcprivacy", """<plist><dict>
<key>NSPrivacyCollectedDataTypes</key>
<array/>
<key>NSPrivacyTracking</key>
<false/>
</dict></plist>""")
        write(self.proj, "src/api.ts",
              "export const upload = (d) => api.post('/metrics', d);")
        self.assertIsNotNone(sev(run_scan(IOS_SCAN, self.proj),
                                 "PRIVACY-MANIFEST-EMPTY"))

    def test_populated_privacy_manifest_is_not_flagged(self):
        write(self.proj, "ios/App/PrivacyInfo.xcprivacy", """<plist><dict>
<key>NSPrivacyCollectedDataTypes</key>
<array><dict><key>NSPrivacyCollectedDataType</key>
<string>NSPrivacyCollectedDataTypeHealthFitness</string></dict></array>
</dict></plist>""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "PRIVACY-MANIFEST-EMPTY"))

    def test_merged_manifest_is_found_under_build_dir(self):
        """SKIP_DIRS contains 'build', so merged manifests were unreachable by
        construction and the advisory could never be satisfied."""
        write(self.proj, "android/app/src/main/AndroidManifest.xml", "<manifest/>")
        write(self.proj,
              "android/app/build/intermediates/merged_manifests/release/AndroidManifest.xml",
              '<manifest><uses-permission android:name="android.permission.CAMERA"/></manifest>')
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "MERGED-MANIFEST-NOT-CHECKED"))

    def test_old_agp_blocks_the_target_sdk_fix(self):
        """an RN 0.49 project is on AGP 2.2.3, which predates App Bundles entirely.
        Telling it to raise targetSdk without saying so hands over a fix that
        cannot be applied."""
        write(self.proj, "android/build.gradle",
              "buildscript { dependencies { classpath 'com.android.tools.build:gradle:2.2.3' } }")
        write(self.proj, "android/app/build.gradle",
              "android { defaultConfig { targetSdkVersion 22 } }")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj), "AGP-TOO-OLD"), "BLOCKER")

    def test_modern_agp_is_not_flagged(self):
        write(self.proj, "android/build.gradle",
              "buildscript { dependencies { classpath 'com.android.tools.build:gradle:8.7.2' } }")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "AGP-TOO-OLD"))


class TestFleetFalsePositives(ScannerTestBase):
    """Found by running both scanners across 34 real projects."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def test_rn_template_debug_keystore_is_not_a_secret(self):
        """'android'/'androiddebugkey' are the public values RN ships in every
        project. Flagging them was half of all signing findings fleet-wide."""
        write(self.proj, "android/app/build.gradle", """
android { signingConfigs {
    debug {
      storeFile file('debug.keystore')
      storePassword 'android'
      keyAlias 'androiddebugkey'
      keyPassword 'android'
    }
} }
""")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "SIGNING-SECRET-COMMITTED"))

    def test_release_keystore_password_still_flagged_alongside_debug(self):
        """Guard: the debug allowlist must not hide a real release credential
        sitting in the same file."""
        write(self.proj, "android/app/build.gradle", """
android { signingConfigs {
    debug {
      storePassword 'android'
      keyAlias 'androiddebugkey'
      keyPassword 'android'
    }
    release {
      storePassword 'RealProductionSecret99'
      keyAlias 'upload'
      keyPassword 'RealProductionSecret99'
    }
} }
""")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SIGNING-SECRET-COMMITTED"), "HIGH")

    def test_permission_not_reported_once_per_build_output_copy(self):
        """AGP writes the same manifest into merged_manifest, merged_manifests,
        bundle_manifest and packaged_manifests. One permission, one finding."""
        perm = ('<manifest><uses-permission '
                'android:name="android.permission.SYSTEM_ALERT_WINDOW"/></manifest>')
        write(self.proj, "android/app/src/main/AndroidManifest.xml", perm)
        for d in ("merged_manifest/release", "merged_manifests/release",
                  "bundle_manifest/release", "packaged_manifests/release"):
            write(self.proj, f"android/app/build/intermediates/{d}/AndroidManifest.xml", perm)
        hits = [f for f in run_scan(ANDROID_SCAN, self.proj)["findings"]
                if f["id"] == "PERM-SYSTEM_ALERT_WINDOW"]
        self.assertEqual(len(hits), 1, f"expected 1 finding, got {len(hits)}")

    def test_translation_string_is_not_a_blocking_secret(self):
        """Rocket.Chat: a German locale file has
        `Certificate_password: 'Zertifikats-Passwort'` — a translated label.
        Downgraded rather than suppressed, matching how every other
        non-production path is treated: still visible, never a blocker."""
        write(self.proj, "app/i18n/locales/de.js",
              "export default {\n  Certificate_password: 'Zertifikats-Passwort',\n};")
        self.assertNotIn(sev(run_scan(IOS_SCAN, self.proj), "SECRET-HARDCODED"),
                         ("BLOCKER", "HIGH"))


    def test_key_alias_alone_is_not_a_credential(self):
        """A key alias is a name, not a secret. It was a third of every signing
        finding across the fleet."""
        write(self.proj, "android/app/build.gradle",
              "android { signingConfigs { release { keyAlias 'upload' } } }")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "SIGNING-SECRET-COMMITTED"))

    def test_store_password_is_still_a_credential(self):
        write(self.proj, "android/app/build.gradle",
              "android { signingConfigs { release { storePassword 'RealSecret2050' } } }")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SIGNING-SECRET-COMMITTED"), "HIGH")

    def test_google_maps_key_is_reported_as_unrestricted_not_as_a_leak(self):
        """AIza client keys are designed to ship — they are secured by bundle-id
        restriction, not secrecy. 90 of 106 BLOCKERs fleet-wide were these."""
        write(self.proj, "src/maps.ts",
              'const KEY = "AIzaSyC1234567890abcdefghijklmnopqrstuv";')
        result = run_scan(IOS_SCAN, self.proj)
        self.assertIsNone(sev(result, "SECRET-HARDCODED"))
        self.assertEqual(sev(result, "MAPS-KEY-RESTRICTION"), "MEDIUM")


    def test_editor_local_history_is_not_scanned(self):
        """one fleet project: VS Code's Local History extension keeps timestamped
        copies under .history/, so one key was reported 8 times."""
        write(self.proj, ".history/app/config/app_20250418190644.ts",
              "export const cfg = { awsKey: 'AKIAIOSFODNN7EXAMPLE' };")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SECRET-HARDCODED"))

    def test_action_type_constant_is_not_a_secret(self):
        """one fleet project: a Redux action type whose value is its own name —
        `SUBMIT_SEND_CLIENT_NEW_PASSWORD = 'SUBMIT_SEND_CLIENT_NEW_PASSWORD'`."""
        write(self.proj, "src/login/loginConstants.js",
              "export const SUBMIT_SEND_CLIENT_NEW_PASSWORD = "
              "'SUBMIT_SEND_CLIENT_NEW_PASSWORD';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SECRET-HARDCODED"))

    def test_named_google_key_is_a_maps_finding_not_a_leak(self):
        """`googleAPIKey: 'AIza...'` was still reaching SECRET-HARDCODED through
        the generic api-key alternate, contradicting the AIza reclassification."""
        write(self.proj, "app/config/app.ts",
              "export default { googleAPIKey: 'AIzaSyD1D6RKYjAMkyQa0rtut-kOmcZVe7VSdJY' };")
        result = run_scan(IOS_SCAN, self.proj)
        self.assertIsNone(sev(result, "SECRET-HARDCODED"))
        self.assertEqual(sev(result, "MAPS-KEY-RESTRICTION"), "MEDIUM")

    def test_play_service_account_private_key_is_still_a_blocker(self):
        """Guard: four projects commit fastlane/google-play-api.json with a Play
        publishing private key. That must never stop being a BLOCKER."""
        write(self.proj, "fastlane/google-play-api.json",
              '{"private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqh"}')
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SECRET-HARDCODED"), "BLOCKER")


class TestCitationAccuracy(ScannerTestBase):
    """A report citing a guideline number that says something else gets the
    whole report dismissed. Verified against the 8 Jun 2026 guidelines."""

    # Numbers that do not exist, or whose subject is not what we used to claim.
    WRONG = {
        "2.5.18": "advertising placement, not crypto mining",
        "2.5.13": "facial recognition, not purchase validation",
        "2.5.14": "recording consent, not authentication APIs",
        "3.1.6": "does not exist (Apple Pay is 4.9)",
        "3.1.7": "does not exist",
    }

    def test_no_finding_cites_a_wrong_guideline_number(self):
        for f in run_scan(IOS_SCAN, self.dirty)["findings"]:
            cited = (f.get("guideline") or "").split(" / ")
            for number in cited:
                self.assertNotIn(number.strip(), self.WRONG,
                                 f"{f['id']} cites {number}: {self.WRONG.get(number.strip())}")

    def test_external_payment_finding_names_the_us_storefront_carve_out(self):
        """3.1.1(a): entitlements are NOT required for external purchase links
        in the United States storefront. Calling it a flat BLOCKER tells a US
        app that a legal monetization path blocks its release."""
        for f in run_scan(IOS_SCAN, self.dirty)["findings"]:
            if f["id"] == "EXTERNAL-PAYMENT":
                self.assertIn("storefront", f["description"].lower())
                return
        self.fail("EXTERNAL-PAYMENT did not fire on the dirty fixture")


class TestRejectionDrivenChecks(ScannerTestBase):
    """Gaps exposed by a real App Store rejection letter for a health app.
    Each docstring quotes the reviewer's own wording."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@invertase/react-native-apple-authentication":"2.3.0"}}')

    def test_profile_completion_after_apple_signin_is_flagged(self):
        """'users are required to provide their name and/or email address after
        using Sign in with Apple even though that information is already
        provided by the Authentication Services framework.'"""
        write(self.proj, "src/auth/AppleSignIn.tsx", """
import { appleAuth } from '@invertase/react-native-apple-authentication';
export async function signIn() {
  const res = await appleAuth.performRequest();
  navigation.navigate('CompleteProfile');
}
""")
        write(self.proj, "src/auth/CompleteProfile.tsx",
              'export function CompleteProfile() { return <TextInput placeholder="Full name" />; }')
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SIWA-REDUNDANT-PROFILE"), "HIGH")

    def test_apple_signin_without_profile_form_is_silent(self):
        write(self.proj, "src/auth/AppleSignIn.tsx", """
import { appleAuth } from '@invertase/react-native-apple-authentication';
export async function signIn() {
  const res = await appleAuth.performRequest();
  await api.post('/session', { identityToken: res.identityToken });
}
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SIWA-REDUNDANT-PROFILE"))


class TestMedicalChecks(ScannerTestBase):
    """Guideline 1.4.1, verified against the live text 2026-09-28."""

    HEALTH_PKG = ('{"dependencies":{"react-native":"0.76.0",'
                  '"@kingstinct/react-native-healthkit":"13.0.0"}}')

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)

    def test_health_app_without_disclaimer_is_flagged(self):
        """'The app provides medical diagnoses or treatment advice but does not
        include the required medical disclaimer.'"""
        write(self.proj, "package.json", self.HEALTH_PKG)
        write(self.proj, "src/Insights.tsx",
              "export const advice = 'Your cholesterol suggests starting treatment.';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "MEDICAL-NO-DISCLAIMER"), "HIGH")

    def test_health_app_with_disclaimer_is_silent(self):
        write(self.proj, "package.json", self.HEALTH_PKG)
        write(self.proj, "src/Insights.tsx",
              "export const advice = 'Your cholesterol suggests starting treatment.';")
        write(self.proj, "src/Disclaimer.tsx",
              "export const TEXT = 'This app does not provide medical advice. Always "
              "consult your physician before making medical decisions.';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "MEDICAL-NO-DISCLAIMER"))

    def test_health_app_with_citations_is_silent(self):
        write(self.proj, "package.json", self.HEALTH_PKG)
        write(self.proj, "src/Insights.tsx",
              "export const advice = { text: 'Cholesterol guidance', "
              "source: 'https://pubmed.ncbi.nlm.nih.gov/12345678/' };")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "MEDICAL-NO-CITATION"))

    def test_non_health_app_never_sees_medical_findings(self):
        """Guard: without health signals these must stay silent, or they fire on
        every project in a fleet."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')
        write(self.proj, "src/Shop.tsx", "export const price = 10;")
        for check in ("MEDICAL-NO-DISCLAIMER", "MEDICAL-NO-CITATION", "SENSOR-ONLY-VITALS"):
            self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), check), check)

    def test_sensor_only_vitals_claim_is_blocker(self):
        """1.4.1: 'apps that claim to take x-rays, measure blood pressure, body
        temperature, blood glucose levels, or blood oxygen levels using only the
        sensors on the device are not permitted.'"""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-vision-camera":"4.0.0"}}')
        write(self.proj, "src/BP.tsx",
              "export const title = 'Measure your blood pressure with the camera';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SENSOR-ONLY-VITALS"), "BLOCKER")

    def test_vitals_from_external_device_is_not_flagged(self):
        """Guard: a reading from a paired cleared device is the compliant path."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-ble-plx":"3.0.0"}}')
        write(self.proj, "src/BP.tsx",
              "export const title = 'Sync blood pressure from your monitor';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SENSOR-ONLY-VITALS"))


class TestPurchaseCopyChecks(ScannerTestBase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)

    def test_subscription_wording_without_iap_is_flagged(self):
        """A real 2.1(b) hold was caused by in-app copy calling one-time
        purchases 'subscriptions' while no IAP products existed."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@stripe/stripe-react-native":"0.38.0"}}')
        write(self.proj, "src/Paywall.tsx",
              "export const copy = 'Manage your subscription';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SUBSCRIPTION-COPY-MISMATCH"), "MEDIUM")

    def test_subscription_wording_with_iap_present_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-iap":"12.0.0"}}')
        write(self.proj, "src/Paywall.tsx",
              "export const copy = 'Manage your subscription';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "SUBSCRIPTION-COPY-MISMATCH"))

    def test_data_model_subscription_is_not_purchase_copy(self):
        """Rocket.Chat: 'subscriptions.get' is its room subscription data model.
        GraphQL and RxJS subscriptions are the same shape. None are purchases."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@stripe/stripe-react-native":"0.38.0"}}')
        write(self.proj, "src/rooms.js", """
export const getRooms = () => sdk.get('subscriptions.get', { updatedSince });
const sub = observable.subscribe(next);
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "SUBSCRIPTION-COPY-MISMATCH"))

    def test_no_subscription_wording_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@stripe/stripe-react-native":"0.38.0"}}')
        write(self.proj, "src/Paywall.tsx",
              "export const copy = 'Buy the 3-month program';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "SUBSCRIPTION-COPY-MISMATCH"))


class TestHealthConnectPermissions(ScannerTestBase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"react-native-health-connect":"3.5.0"}}')

    def test_declared_health_permission_never_read_is_flagged(self):
        """Health Connect access is granted per data type against a declared use
        case, so a type the code never reads is an over-request."""
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.health.READ_STEPS"/>
  <uses-permission android:name="android.permission.health.READ_BLOOD_PRESSURE"/>
</manifest>""")
        write(self.proj, "src/health.ts", "readRecords('Steps');")
        result = run_scan(ANDROID_SCAN, self.proj)
        self.assertEqual(sev(result, "HEALTH-PERM-UNUSED"), "HIGH")
        hit = [f for f in result["findings"] if f["id"] == "HEALTH-PERM-UNUSED"][0]
        self.assertIn("BloodPressure", hit["description"])
        self.assertNotIn("Steps", hit["description"])

    def test_all_health_permissions_used_is_silent(self):
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><uses-permission '
              'android:name="android.permission.health.READ_STEPS"/></manifest>')
        write(self.proj, "src/health.ts", "readRecords('Steps');")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "HEALTH-PERM-UNUSED"))

    def test_no_health_permissions_declared_is_silent(self):
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><uses-permission android:name="android.permission.INTERNET"/></manifest>')
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "HEALTH-PERM-UNUSED"))


class TestAIContentPolicy(ScannerTestBase):
    """Play: apps that generate AI content must provide in-app reporting or
    flagging of offensive content, without leaving the app."""

    AI_PKG = '{"dependencies":{"react-native":"0.76.0","openai":"4.0.0"}}'

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)

    def test_ai_chat_without_in_app_reporting_is_flagged(self):
        write(self.proj, "package.json", self.AI_PKG)
        write(self.proj, "src/Chat.tsx",
              "const res = await openai.chat.completions.create({ messages });")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "AI-CONTENT-NO-REPORT"), "HIGH")

    def test_ai_chat_with_reporting_is_silent(self):
        write(self.proj, "package.json", self.AI_PKG)
        write(self.proj, "src/Chat.tsx",
              "const res = await openai.chat.completions.create({ messages });")
        write(self.proj, "src/Report.tsx",
              "export const reportContent = (id, reason) => api.post('/reports', { id, reason });")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "AI-CONTENT-NO-REPORT"))

    def test_english_word_replicate_is_not_a_model_sdk(self):
        """one fleet project: medical prose 'the mycobacteria continue to replicate
        inside immune cells' matched the Replicate SDK. Same class as the
        historical 'adjust' bug — match package names, never bare words."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')
        write(self.proj, "src/Article.tsx",
              "export const text = 'The mycobacteria continue to replicate inside "
              "immune cells, causing a local lesion.';")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "AI-CONTENT-NO-REPORT"))

    def test_replicate_as_an_actual_dependency_is_detected(self):
        """Guard: the real SDK must still be found."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","replicate":"0.34.0"}}')
        write(self.proj, "src/Gen.tsx", "import Replicate from 'replicate';")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "AI-CONTENT-NO-REPORT"), "HIGH")

    def test_app_with_no_model_sdk_is_silent(self):
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')
        write(self.proj, "src/Chat.tsx", "export const x = 1;")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "AI-CONTENT-NO-REPORT"))


class TestReviewFindings(ScannerTestBase):
    """Findings from the whole-branch review, each reproduced before fixing."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)

    # --- C2: permission name != record type name
    def test_health_record_types_that_differ_from_permission_names(self):
        """READ_EXERCISE is ExerciseSession, READ_SLEEP is SleepSession,
        READ_HEART_RATE_VARIABILITY is HeartRateVariabilityRmssd. Naive
        PascalCase told teams to delete permissions they actively read."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"react-native-health-connect":"3.5.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.health.READ_EXERCISE"/>
  <uses-permission android:name="android.permission.health.READ_SLEEP"/>
  <uses-permission android:name="android.permission.health.READ_HEART_RATE_VARIABILITY"/>
  <uses-permission android:name="android.permission.health.READ_VO2_MAX"/>
</manifest>""")
        write(self.proj, "src/health.ts", """
readRecords('ExerciseSession');
readRecords('SleepSession');
readRecords('HeartRateVariabilityRmssd');
readRecords('Vo2Max');
""")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "HEALTH-PERM-UNUSED"))

    def test_capability_permissions_are_not_record_types(self):
        """READ_HEALTH_DATA_IN_BACKGROUND and READ_HEALTH_DATA_HISTORY are
        capability grants with no record type, so they were wrong 100% of the
        time."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"react-native-health-connect":"3.5.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND"/>
  <uses-permission android:name="android.permission.health.READ_HEALTH_DATA_HISTORY"/>
</manifest>""")
        write(self.proj, "src/health.ts", "readRecords('Steps');")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "HEALTH-PERM-UNUSED"))

    def test_genuinely_unused_type_is_still_reported(self):
        """Guard: the check must keep working after the mapping fix."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"react-native-health-connect":"3.5.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.health.READ_STEPS"/>
  <uses-permission android:name="android.permission.health.READ_BLOOD_PRESSURE"/>
</manifest>""")
        write(self.proj, "src/health.ts", "readRecords('Steps');")
        r = run_scan(ANDROID_SCAN, self.proj)
        self.assertEqual(sev(r, "HEALTH-PERM-UNUSED"), "HIGH")
        hit = [f for f in r["findings"] if f["id"] == "HEALTH-PERM-UNUSED"][0]
        self.assertIn("BloodPressure", hit["description"])

    # --- I3: the health gate must not be tripped by ordinary English
    def test_ordinary_english_does_not_make_an_app_a_health_app(self):
        """'Thanks for being patient' and a Diagnostics screen are not health
        signals. This gate firing wrongly puts medical findings on every app."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')
        write(self.proj, "src/Copy.tsx",
              "export const copy = 'Thanks for being patient while we upgrade.';\n"
              "export const faq = 'How do I treat a stain? See our treatment guide.';")
        write(self.proj, "src/Diagnostics.tsx", "export function runDiagnostics() {}")
        for check in ("MEDICAL-NO-DISCLAIMER", "MEDICAL-NO-CITATION"):
            self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), check), check)

    def test_web_vitals_dependency_is_not_a_health_signal(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","web-vitals":"4.2.0"}}')
        write(self.proj, "src/Perf.tsx", "export const x = 'diagnostics';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "MEDICAL-NO-DISCLAIMER"))

    def test_real_health_app_is_still_gated_in(self):
        """Guard: a genuine health app must still get the medical checks."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/Insights.tsx",
              "export const advice = 'Your cholesterol suggests treatment.';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "MEDICAL-NO-DISCLAIMER"), "HIGH")


    # --- I4: the rebuttal half of an absence check must see locale files
    def test_disclaimer_in_a_locale_file_counts(self):
        """RN apps keep user-facing copy in i18n/. _grep skips those paths, so
        the trigger survived the skip-list and the rebuttal did not."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/SymptomScreen.tsx",
              "export const s = 'Review your symptoms and cholesterol trend';")
        write(self.proj, "src/locales/en.json",
              '{"disclaimer":"This app does not provide medical advice. Consult your '
              'physician.","sources":"Sources: https://pubmed.ncbi.nlm.nih.gov/1/"}')
        for check in ("MEDICAL-NO-DISCLAIMER", "MEDICAL-NO-CITATION"):
            self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), check), check)

    # --- I5: a camera in package.json is not evidence of a sensor measurement
    def test_external_device_vocabulary_suppresses_sensor_only(self):
        """'Read blood oxygen recorded by your Apple Watch' in an app that also
        uses the camera for avatars is the compliant path, not a BLOCKER."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","expo-camera":"15.0.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/Spo2.tsx",
              "export const t = 'Read blood oxygen recorded by your Apple Watch';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SENSOR-ONLY-VITALS"))

    def test_manual_entry_of_a_vital_is_not_sensor_only(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","expo-sensors":"13.0.0"}}')
        write(self.proj, "src/Temp.tsx",
              "export const t = 'Take a body temperature reading with a thermometer "
              "and enter it here';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SENSOR-ONLY-VITALS"))

    def test_camera_based_vital_claim_is_still_blocker(self):
        """Guard: the real violation must survive the narrowing."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-vision-camera":"4.0.0"}}')
        write(self.proj, "src/BP.tsx",
              "export const t = 'Measure your blood pressure using the camera';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SENSOR-ONLY-VITALS"), "BLOCKER")

    # --- I6: SIWA needs evidence of a name/email field, not a screen name
    def test_profile_screen_without_name_or_email_field_is_silent(self):
        """Asking for height, weight and a goal is not the cited violation."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@invertase/react-native-apple-authentication":"2.3.0"}}')
        write(self.proj, "src/ProfileSetup.tsx",
              "export function ProfileSetup() { return <NumberInput label='Height (cm)' />; }")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SIWA-REDUNDANT-PROFILE"))

    # --- I7: mainstream IAP libraries must count
    def test_modern_iap_libraries_suppress_subscription_copy(self):
        for dep in ("react-native-adapty", "expo-iap", "react-native-purchases-ui"):
            proj = tempfile.mkdtemp(dir=self.tmp)
            write(proj, "package.json",
                  '{"dependencies":{"react-native":"0.76.0","%s":"1.0.0"}}' % dep)
            write(proj, "src/Paywall.tsx", "export const c = 'Manage your subscription';")
            self.assertIsNone(sev(run_scan(IOS_SCAN, proj),
                                  "SUBSCRIPTION-COPY-MISMATCH"), dep)

    def test_graphql_subscription_near_the_word_plan_is_not_purchase_copy(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@stripe/stripe-react-native":"0.38.0"}}')
        write(self.proj, "src/api.ts",
              "// plan: move these subscriptions into a shared client\n"
              "export const TICKET_SUB = gql`subscription OnTicket { id }`;")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "SUBSCRIPTION-COPY-MISMATCH"))


class TestSecondRejectionRound(ScannerTestBase):
    """A second rejection round on the same app, 30 Sep 2026."""

    UGC = ("export const createPost = b => api.post('/posts', b);\n"
           "export const postComment = c => api.post('/comments', c);\n")

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def test_reporting_without_self_service_block_is_flagged(self):
        """Apple credited reporting and admin moderation but still required a
        self-service block the user controls on the spot. The old check went
        quiet as soon as ANY moderation path existed."""
        write(self.proj, "src/Feed.tsx", self.UGC +
              "export const reportContent = (id, r) => api.post('/reports', { id, r });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "UGC-BLOCK-MISSING"), "HIGH")

    def test_block_present_is_silent(self):
        write(self.proj, "src/Feed.tsx", self.UGC +
              "export const reportContent = (id, r) => api.post('/reports', { id, r });\n"
              "export const blockUser = id => api.post('/blocks', { id });")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "UGC-BLOCK-MISSING"))

    def test_post_reporting_without_comment_reporting_is_flagged(self):
        """'Add the ability to report individual comments (today only whole
        posts can be reported).'"""
        write(self.proj, "src/Feed.tsx", self.UGC +
              "export const reportPost = id => api.post('/reports/post', { id });\n"
              "export const blockUser = id => api.post('/blocks', { id });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "UGC-COMMENT-REPORT-MISSING"), "MEDIUM")

    def test_comment_reporting_present_is_silent(self):
        write(self.proj, "src/Feed.tsx", self.UGC +
              "export const reportComment = id => api.post('/reports/comment', { id });\n"
              "export const blockUser = id => api.post('/blocks', { id });")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "UGC-COMMENT-REPORT-MISSING"))

    def test_healthkit_type_requested_but_never_read_is_flagged(self):
        """'Remove an unused permission so our declared Apple Health access
        exactly matches what the app actually uses.' Android already had this
        check; iOS did not."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/health.ts", """
const PERMS = ['HKQuantityTypeIdentifierStepCount',
               'HKQuantityTypeIdentifierBloodGlucose'];
export const read = () => queryQuantitySamples('HKQuantityTypeIdentifierStepCount');
""")
        r = run_scan(IOS_SCAN, self.proj)
        self.assertEqual(sev(r, "HEALTHKIT-PERM-UNUSED"), "HIGH")
        hit = [f for f in r["findings"] if f["id"] == "HEALTHKIT-PERM-UNUSED"][0]
        self.assertIn("BloodGlucose", hit["description"])
        self.assertNotIn("StepCount", hit["description"])

    def test_type_wired_through_a_mapping_table_is_not_unused(self):
        """The real shape: a permissions array plus a metric mapping plus a
        formatter. No line carries a query verb, but the type is clearly wired
        in. Occurrence count is the robust signal, not line context."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/perms.ts",
              "export const READ = ['HKQuantityTypeIdentifierStepCount'];")
        write(self.proj, "src/map.ts",
              "export const M = { steps: 'HKQuantityTypeIdentifierStepCount' };")
        write(self.proj, "src/fmt.ts",
              "export const label = t => t === 'HKQuantityTypeIdentifierStepCount' ? 'Steps' : '';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "HEALTHKIT-PERM-UNUSED"))

    def test_all_healthkit_types_read_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/health.ts",
              "const PERMS = ['HKQuantityTypeIdentifierStepCount'];\n"
              "export const read = () => query('HKQuantityTypeIdentifierStepCount');")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "HEALTHKIT-PERM-UNUSED"))

    def test_passkit_linked_without_apple_pay_usage_is_flagged(self):
        """Verbatim 2.1: 'The app binary includes the PassKit framework for
        implementing Apple Pay, but we were unable to verify any integration of
        Apple Pay within the app.'"""
        write(self.proj, "ios/Podfile.lock",
              "PODS:\n  - Stripe (23.0.0)\n\nFRAMEWORKS:\n  - PassKit\n")
        write(self.proj, "src/Pay.tsx", "export const checkout = () => api.post('/charge');")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "FRAMEWORK-UNUSED"), "HIGH")

    def test_passkit_with_apple_pay_usage_is_silent(self):
        write(self.proj, "ios/Podfile.lock", "FRAMEWORKS:\n  - PassKit\n")
        write(self.proj, "src/Pay.tsx",
              "import { ApplePayButton, useApplePay } from '@stripe/stripe-react-native';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "FRAMEWORK-UNUSED"))


class TestCheckInventoryCompleteness(ScannerTestBase):
    """docs/CHECKS.md is the published inventory. A check missing from it is
    invisible to every user, and gen_checks --check cannot notice because it
    compares its own render against the file it rendered."""

    def _ids_in_source(self, script):
        import re as _re
        src = open(script, encoding="utf-8").read()
        sev = {"BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"}
        ids = set(_re.findall(r'"id":\s*"([A-Z][A-Z0-9\-]+)"', src))
        ids |= set(_re.findall(r'\(\s*"([A-Z][A-Z0-9\-]+)",\s*'
                               r'"(?:BLOCKER|HIGH|MEDIUM|LOW)"', src))
        return ids - sev

    def test_every_emitted_check_is_documented(self):
        docs = open(os.path.join(ROOT, "docs", "CHECKS.md"), encoding="utf-8").read()
        missing = []
        for script in (IOS_SCAN, ANDROID_SCAN):
            for cid in sorted(self._ids_in_source(script)):
                if "`%s`" % cid not in docs:
                    missing.append(cid)
        self.assertEqual(missing, [],
                         "checks emitted by a scanner but absent from docs/CHECKS.md "
                         "(gen_checks.py is dropping them): %s" % ", ".join(missing))


class TestPhase2Apple(ScannerTestBase):
    """Apple coverage gaps, guideline text verified live 2026-09-30."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def _deps(self, **kw):
        d = {"react-native": "0.76.0"}; d.update(kw)
        write(self.proj, "package.json", json.dumps({"dependencies": d}))

    def test_iap_without_finish_transaction_is_flagged(self):
        """2.3.2 / 2.1 — an unfinished transaction re-presents the purchase
        sheet on every launch; the reviewer hits it on the first tap."""
        self._deps(**{"react-native-iap": "12.0.0"})
        write(self.proj, "src/Purchases.tsx",
              "import { initConnection, requestPurchase } from 'react-native-iap';\n"
              "export const buy = sku => requestPurchase({ sku });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "IAP-UNFINISHED-TRANSACTION"), "HIGH")

    def test_iap_with_finish_transaction_is_silent(self):
        self._deps(**{"react-native-iap": "12.0.0"})
        write(self.proj, "src/Purchases.tsx",
              "import { requestPurchase, finishTransaction } from 'react-native-iap';\n"
              "export const done = p => finishTransaction({ purchase: p });")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "IAP-UNFINISHED-TRANSACTION"))

    def test_revenuecat_wrapper_is_not_flagged(self):
        """RevenueCat finishes transactions inside the SDK; exposing no
        finishTransaction is correct there, not a defect."""
        self._deps(**{"react-native-purchases": "8.0.0"})
        write(self.proj, "src/Paywall.tsx",
              "import Purchases from 'react-native-purchases';\n"
              "export const buy = p => Purchases.purchasePackage(p);")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "IAP-UNFINISHED-TRANSACTION"))

    def test_social_login_without_revoke_is_flagged(self):
        """5.1.1(v): 'a mechanism to revoke social network credentials and
        disable data access between the app and social network from within
        the app.' Signing out is not revoking."""
        self._deps(**{"@react-native-google-signin/google-signin": "10.0.0"})
        write(self.proj, "src/Auth.tsx",
              "import { GoogleSignin } from '@react-native-google-signin/google-signin';\n"
              "export const login = () => GoogleSignin.signIn();\n"
              "export const logout = () => GoogleSignin.signOut();")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SOCIAL-REVOKE-MISSING"), "HIGH")

    def test_social_login_with_revoke_is_silent(self):
        self._deps(**{"@react-native-google-signin/google-signin": "10.0.0"})
        write(self.proj, "src/Auth.tsx",
              "import { GoogleSignin } from '@react-native-google-signin/google-signin';\n"
              "export const login = () => GoogleSignin.signIn();\n"
              "export const disconnect = () => GoogleSignin.revokeAccess();")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SOCIAL-REVOKE-MISSING"))

    def test_ads_without_report_control_is_flagged(self):
        """2.5.18: 'Apps that contain ads must also include the ability for
        users to report any inappropriate or age-inappropriate ads.'"""
        self._deps(**{"react-native-google-mobile-ads": "13.0.0"})
        write(self.proj, "src/Banner.tsx",
              "import { BannerAd, BannerAdSize } from 'react-native-google-mobile-ads';\n"
              "export const Ad = () => <BannerAd unitId={U} size={BannerAdSize.BANNER} />;")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "AD-REPORT-MISSING"), "HIGH")

    def test_ads_with_report_control_in_locale_file_is_silent(self):
        """The button label lives in en.json in any localised app."""
        self._deps(**{"react-native-google-mobile-ads": "13.0.0"})
        write(self.proj, "src/Banner.tsx",
              "import { BannerAd } from 'react-native-google-mobile-ads';\n"
              "export const Ad = () => <BannerAd unitId={U} />;")
        write(self.proj, "src/locales/en.json", '{"ads":{"report":"Report this ad"}}')
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "AD-REPORT-MISSING"))

    def test_fbsdk_next_is_not_an_ad_sdk(self):
        """react-native-fbsdk-next is login/analytics; Audience Network is the
        separate react-native-fbads. One prefix apart."""
        self._deps(**{"react-native-fbsdk-next": "13.0.0"})
        write(self.proj, "src/Login.tsx", "import { LoginManager } from 'react-native-fbsdk-next';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "AD-REPORT-MISSING"))

    def test_health_value_into_analytics_is_blocker(self):
        """5.1.2(vi): HealthKit data 'may not be used for marketing,
        advertising or use-based data mining, including by third parties.'"""
        self._deps(**{"react-native-health": "1.18.0",
                      "@react-native-firebase/analytics": "23.0.0"})
        write(self.proj, "src/Analytics.tsx",
              "export const onSync = s => analytics().setUserProperty('blood_glucose', s.bg);")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "HEALTH-DATA-TO-ADS"), "BLOCKER")

    def test_health_app_with_neutral_analytics_is_silent(self):
        """Co-presence of a health SDK and analytics is not a violation."""
        self._deps(**{"react-native-health": "1.18.0",
                      "@react-native-firebase/analytics": "23.0.0"})
        write(self.proj, "src/Analytics.tsx",
              "export const onSync = () => analytics().logEvent('sync_done', "
              "{ source: 'healthkit', duration_ms: 812 });")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "HEALTH-DATA-TO-ADS"))

    def test_media_downloader_package_is_blocker(self):
        """5.2.3 bars the ability to save, convert or download media from
        third-party sources without authorization."""
        self._deps(**{"@distube/ytdl-core": "4.14.4"})
        write(self.proj, "src/Download.ts", "import ytdl from '@distube/ytdl-core';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "MEDIA-DOWNLOADER"), "BLOCKER")

    def test_legitimate_media_libraries_are_silent(self):
        """react-native-video and rn-fetch-blob download media legitimately."""
        self._deps(**{"react-native-video": "6.0.0", "rn-fetch-blob": "0.12.0"})
        write(self.proj, "src/Offline.ts", "import RNFetchBlob from 'rn-fetch-blob';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "MEDIA-DOWNLOADER"))


class TestPhase2Play(ScannerTestBase):
    """Play coverage gaps, policy text verified live 2026-09-30."""

    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def test_template_package_name_is_blocker(self):
        """Play Console Requirements: packages must be registered, and a
        template placeholder cannot be. com.example is RFC 2606-reserved."""
        write(self.proj, "android/app/build.gradle",
              'android { namespace "com.anonymous.dirtyapp"\n'
              '  defaultConfig { applicationId "com.anonymous.dirtyapp"\n'
              '                  targetSdkVersion 36 } }')
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "PACKAGE-NAME-PLACEHOLDER"), "BLOCKER")

    def test_real_package_name_is_silent(self):
        write(self.proj, "android/app/build.gradle",
              'android { namespace "tech.bitsol.claims"\n'
              '  defaultConfig { applicationId "tech.bitsol.claims"\n'
              '                  targetSdkVersion 36 } }')
        write(self.proj, "android/app/src/androidTest/java/com/example/AppTest.java",
              "package com.example;")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "PACKAGE-NAME-PLACEHOLDER"))

    def test_accessibility_service_plus_llm_is_blocker(self):
        """Accessibility API 'cannot be requested for an app that autonomously
        initiates, plans, and executes actions or decisions' (30 Oct 2025)."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","openai":"4.0.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><service android:name=".AgentService"\n'
              '  android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"/></manifest>')
        write(self.proj, "src/Agent.ts",
              "import OpenAI from 'openai';\n"
              "export const run = g => openai.chat.completions.create({ messages: g });")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "ACCESSIBILITY-AGENTIC-AUTOMATION"), "BLOCKER")

    def test_accessibility_props_without_a_service_are_silent(self):
        """RN a11y props and testing libraries must never match."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","openai":"4.0.0"}}')
        write(self.proj, "src/Button.tsx",
              '<Pressable accessibilityRole="button" accessibilityLabel="Submit" />')
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "ACCESSIBILITY-AGENTIC-AUTOMATION"))

    def test_deterministic_automation_without_llm_is_silent(self):
        """Rule-based automation is explicitly still permitted."""
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><service android:name=".MacroService"\n'
              '  android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"/></manifest>')
        write(self.proj, "src/Macro.ts", "export const tap = n => performGlobalAction(n);")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "ACCESSIBILITY-AGENTIC-AUTOMATION"))

    def test_android_mining_parity(self):
        """The iOS scanner catches on-device mining; Android was blind."""
        write(self.proj, "src/Miner.ts",
              "const POOL = 'stratum+tcp://xmr.pool.example:3333';")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj), "MINING"), "BLOCKER")

    def test_hashrate_chart_is_not_mining(self):
        write(self.proj, "src/Chart.tsx",
              "export const Stats = ({ hashrate }) => <Text>{hashrate} TH/s</Text>;")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "MINING"))

    def test_incentivized_rating_is_flagged(self):
        """Store Listing: bans 'offering users a discount in exchange for a
        high rating.'"""
        write(self.proj, "src/Banner.tsx",
              "export const C = 'Rate us 5 stars to unlock a free month of Pro!';")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "INCENTIVIZED-RATING"), "HIGH")

    def test_rewarded_ads_are_not_incentivized_ratings(self):
        """'reward' collides head-on with ad SDKs."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"react-native-google-mobile-ads":"13.0.0"}}')
        write(self.proj, "src/Ads.ts",
              "import { RewardedAd } from 'react-native-google-mobile-ads';\n"
              "export const onRewardEarned = () => grantCoins(50);")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "INCENTIVIZED-RATING"))

    def test_separate_user_does_not_match_rate_us(self):
        """Re-pin the historical 'sepaRATE USer' false positive."""
        write(self.proj, "src/Util.ts",
              "export const splitUsers = () => separate users into cohorts;")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "INCENTIVIZED-RATING"))

    def test_store_listing_title_too_long_is_flagged(self):
        write(self.proj, "android/app/src/main/res/values/strings.xml",
              '<resources><string name="app_name">'
              '🔥 BEST CLAIMS APP EVER — #1 Insurance Helper!!</string></resources>')
        self.assertIsNotNone(sev(run_scan(ANDROID_SCAN, self.proj), "STORE-LISTING-TITLE"))

    def test_localized_strings_xml_is_not_checked(self):
        """A localized app_name is a translation; character budgets and ALL CAPS
        do not transfer, and 14 locale files would become 14 findings."""
        write(self.proj, "android/app/src/main/res/values/strings.xml",
              '<resources><string name="app_name">Bitsol Claims</string></resources>')
        write(self.proj, "android/app/src/main/res/values-de/strings.xml",
              '<resources><string name="app_name">'
              'BITSOL SCHADENSMELDUNG UND ERSTATTUNG BEANTRAGEN</string></resources>')
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "STORE-LISTING-TITLE"))


class TestPhase2AppleB(ScannerTestBase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def _deps(self, **kw):
        d = {"react-native": "0.76.0"}; d.update(kw)
        write(self.proj, "package.json", json.dumps({"dependencies": d}))

    def test_push_gate_without_skip_is_flagged(self):
        """4.5.4: 'Push Notifications must not be required for the app to
        function.' 5.1.2(i) bars requiring system functionality for access."""
        self._deps(**{"expo-notifications": "0.29.0"})
        write(self.proj, "src/Gate.tsx", """
import * as Notifications from 'expo-notifications';
export function Gate({ navigation }) {
  if (status !== 'granted') {
    return <View><Text>Notifications are required to continue.</Text></View>;
  }
  navigation.replace('Home');
}
""")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "PUSH-REQUIRED-GATE"), "HIGH")

    def test_push_primer_with_skip_is_silent(self):
        self._deps(**{"expo-notifications": "0.29.0"})
        write(self.proj, "src/Primer.tsx", """
import * as Notifications from 'expo-notifications';
export function Primer({ navigation }) {
  if (status !== 'granted') { return <Button title="Not now" onPress={skip} />; }
}
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "PUSH-REQUIRED-GATE"))

    def test_location_gate_is_not_a_push_gate(self):
        """A maps app legitimately cannot proceed without location; including
        expo-location would fire on a large share of real apps."""
        self._deps(**{"expo-location": "18.0.0"})
        write(self.proj, "src/Gate.tsx", """
import * as Location from 'expo-location';
export function Gate({ navigation }) {
  if (status !== 'granted') { return <View><Text>Location required.</Text></View>; }
  navigation.replace('Map');
}
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "PUSH-REQUIRED-GATE"))

    def test_device_restart_copy_is_flagged(self):
        """2.4.4: 'Apps should never suggest or require a restart of the device
        or modifications to system settings.'"""
        write(self.proj, "src/locales/en.json",
              '{"help":"For background sync, turn off Low Power Mode and restart your device."}')
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "SYSTEM-SETTINGS-PROMPT"), "MEDIUM")

    def test_restart_the_app_is_not_a_device_restart(self):
        write(self.proj, "src/Help.ts",
              "export const H = 'If sync stalls, pull to refresh or restart the app.';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SYSTEM-SETTINGS-PROMPT"))

    def test_review_incentive_is_flagged(self):
        """5.6.3 Discovery Fraud; §3 preamble escalates to expulsion."""
        write(self.proj, "src/RateUs.tsx",
              "export const C = 'Rate us 5 stars on the App Store and get 100 free credits!';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "REVIEW-INCENTIVE"), "HIGH")

    def test_rating_something_other_than_the_app_is_silent(self):
        write(self.proj, "src/Workout.tsx",
              "export const C = 'Rate your workout to earn 10 points.';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "REVIEW-INCENTIVE"))

    def test_contacts_select_all_is_flagged(self):
        """5.1.2(v): 'do not include a Select All option or default the
        selection of all contacts.'"""
        self._deps(**{"expo-contacts": "13.0.0"})
        write(self.proj, "src/Invite.tsx",
              "import * as Contacts from 'expo-contacts';\n"
              "export const Invite = () => <Button title=\"Select all\" onPress={all} />;")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "CONTACTS-SELECT-ALL"), "HIGH")

    def test_select_all_outside_a_contacts_file_is_silent(self):
        """A repo-wide grep for 'select all' is unusable — photo pickers,
        tables and todo lists all have one."""
        self._deps(**{"expo-contacts": "13.0.0"})
        write(self.proj, "src/Invite.tsx",
              "import * as Contacts from 'expo-contacts';\n"
              "export const Invite = () => <ContactRow onToggle={t} />;")
        write(self.proj, "src/Gallery.tsx",
              'export const G = () => <Button title="Select all" onPress={allPhotos} />;')
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "CONTACTS-SELECT-ALL"))

    def test_sweepstakes_without_rules_is_flagged(self):
        """5.3.2: official rules must be in the app and state Apple is not a
        sponsor."""
        write(self.proj, "src/locales/en.json",
              '{"promo":"Enter to win an iPhone! Join the sweepstakes"}')
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "SWEEPSTAKES-NO-RULES"), "MEDIUM")

    def test_sweepstakes_with_rules_is_silent(self):
        write(self.proj, "src/locales/en.json",
              '{"promo":"Enter to win an iPhone!",'
              '"rules":"Official Rules: no purchase necessary. Apple is not a sponsor of '
              'or involved in this promotion in any manner."}')
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "SWEEPSTAKES-NO-RULES"))

    def test_volume_switch_override_is_flagged(self):
        """2.5.9 bars altering or disabling standard switches."""
        self._deps(**{"react-native-volume-manager": "1.10.0"})
        write(self.proj, "src/Player.tsx",
              "import { VolumeManager } from 'react-native-volume-manager';\n"
              "VolumeManager.showNativeVolumeUI({ enabled: false });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "VOLUME-BUTTON-OVERRIDE"), "MEDIUM")

    def test_media_player_volume_prop_is_silent(self):
        """An in-app volume slider does not touch the hardware switches."""
        self._deps(**{"react-native-video": "6.0.0"})
        write(self.proj, "src/Player.tsx",
              "import Video from 'react-native-video';\n"
              "export const P = ({ vol }) => <Video source={S} volume={vol} />;")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "VOLUME-BUTTON-OVERRIDE"))


class TestPhase2PlayB(ScannerTestBase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')

    def _deps(self, **kw):
        d = {"react-native": "0.76.0"}; d.update(kw)
        write(self.proj, "package.json", json.dumps({"dependencies": d}))

    def test_read_contacts_without_picker_is_flagged(self):
        """Contacts Permissions policy, deadline 27 Jan 2027: use the Android
        Contact Picker unless a Console declaration proves it insufficient."""
        self._deps(**{"expo-contacts": "13.0.0"})
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><uses-permission '
              'android:name="android.permission.READ_CONTACTS"/></manifest>')
        write(self.proj, "src/Invite.ts",
              "import * as Contacts from 'expo-contacts';\n"
              "export const all = () => Contacts.getContactsAsync();")
        self.assertIsNotNone(sev(run_scan(ANDROID_SCAN, self.proj),
                                 "CONTACTS-PICKER-REQUIRED"))

    def test_contact_picker_is_silent(self):
        self._deps(**{"expo-contacts": "13.0.0"})
        write(self.proj, "android/app/src/main/AndroidManifest.xml", "<manifest/>")
        write(self.proj, "src/Invite.ts",
              "export const pick = () => Contacts.presentContactPickerAsync();")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "CONTACTS-PICKER-REQUIRED"))

    def test_dialer_app_is_downgraded_not_flagged_high(self):
        """A default dialer is one of the 11 approved use cases."""
        self._deps(**{"react-native-contacts": "8.0.0"})
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.READ_CONTACTS"/>
  <application><activity><intent-filter>
    <action android:name="android.intent.action.DIAL"/>
  </intent-filter></activity></application></manifest>""")
        self.assertNotIn(sev(run_scan(ANDROID_SCAN, self.proj), "CONTACTS-PICKER-REQUIRED"),
                         ("BLOCKER", "HIGH"))

    def test_old_agp_with_target35_flags_16kb_build_config(self):
        """16 KB is a hard publish block from 1 Feb 2027. The existing check
        only fires if someone already built; this is the pre-build half."""
        write(self.proj, "android/build.gradle",
              "buildscript { dependencies { "
              "classpath 'com.android.tools.build:gradle:8.2.1' } }")
        write(self.proj, "android/app/build.gradle",
              "android { defaultConfig { targetSdkVersion 36 } }")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "PAGE-SIZE-16KB-BUILD-CONFIG"), "HIGH")

    def test_modern_agp_and_rn_is_silent(self):
        self._deps(**{"react-native": "0.79.0"})
        write(self.proj, "android/build.gradle",
              "buildscript { dependencies { "
              "classpath 'com.android.tools.build:gradle:8.7.2' } }")
        write(self.proj, "android/app/build.gradle",
              "android { defaultConfig { targetSdkVersion 36 } }")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "PAGE-SIZE-16KB-BUILD-CONFIG"))

    def test_fake_system_notification_is_flagged(self):
        """MUwS: 'We don't allow apps or ads that mimic or interfere with
        system functionality, such as notifications or warnings.'"""
        self._deps(**{"@notifee/react-native": "9.0.0"})
        write(self.proj, "src/Push.ts", """
import notifee from '@notifee/react-native';
await notifee.displayNotification({
  title: 'Security alert detected',
  body: 'Your device is infected. Tap to clean now.',
});
""")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SYSTEM-UI-IMITATION"), "HIGH")

    def test_telehealth_virus_copy_is_silent(self):
        """A clinic app discussing viruses is the false positive that would
        discredit this check."""
        self._deps(**{"@notifee/react-native": "9.0.0"})
        write(self.proj, "src/Health.tsx",
              "export const A = 'If a virus is detected in your sample, "
              "your clinician will call you.';")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "SYSTEM-UI-IMITATION"))

    def test_precise_location_without_coarse_is_flagged(self):
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><uses-permission '
              'android:name="android.permission.ACCESS_FINE_LOCATION"/></manifest>')
        write(self.proj, "src/Near.ts",
              "const p = await Location.getCurrentPositionAsync("
              "{ accuracy: Location.Accuracy.Highest });")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "LOCATION-PRECISE-NO-COARSE"), "MEDIUM")

    def test_coarse_declared_alongside_fine_is_silent(self):
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
  <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
</manifest>""")
        write(self.proj, "src/Near.ts",
              "const p = await Location.getCurrentPositionAsync("
              "{ accuracy: Location.Accuracy.Highest });")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "LOCATION-PRECISE-NO-COARSE"))

    def test_git_dependency_is_flagged(self):
        """Use of SDKs In Apps: you are responsible for third-party code, and
        a git dependency is not resolvable from any registry that audits it."""
        write(self.proj, "package.json", json.dumps({"dependencies": {
            "react-native": "0.76.0",
            "vendor-sdk": "git+https://github.com/vendor/rn-sdk.git#a1b2c3d"}}))
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "SDK-UNAUDITABLE-SOURCE"), "MEDIUM")

    def test_workspace_and_file_refs_are_silent(self):
        """Monorepo-internal references to the team's own packages."""
        write(self.proj, "package.json", json.dumps({"dependencies": {
            "react-native": "0.76.0", "@acme/ds": "workspace:*",
            "shared-types": "file:../packages/shared-types"}}))
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj),
                              "SDK-UNAUDITABLE-SOURCE"))


class TestInterpreterCompatibility(ScannerTestBase):
    """Both scanners must import and run on every supported interpreter.

    A mid-pattern (?i) was deprecated in 3.6 and is an error in 3.11+, so a
    regex that compiles here can still be a hard crash for most users --
    Homebrew and Ubuntu 24.04 ship 3.12/3.13.
    """

    def test_every_scanner_regex_compiles(self):
        import re as _re
        for script in (IOS_SCAN, ANDROID_SCAN):
            src = open(script, encoding="utf-8").read()
            # Any global inline flag that is not at position 0 of its pattern.
            for m in _re.finditer(r'r"(?:[^"\\]|\\.)*"', src):
                lit = m.group(0)[2:-1]
                if "(?i)" in lit and not lit.startswith("(?i)"):
                    self.fail(f"{os.path.basename(script)}: mid-pattern (?i) is a "
                              f"PatternError on Python 3.11+: {lit[:70]}")

    def test_scanners_run_clean_with_deprecation_warnings_as_errors(self):
        for script, platform in ((IOS_SCAN, "ios"), (ANDROID_SCAN, "android")):
            out = subprocess.run(
                [sys.executable, "-W", "error::DeprecationWarning", script,
                 self.dirty, "--format", "json"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(out.returncode, 0,
                             f"{platform} scanner failed under -W error: {out.stderr[-400:]}")
            self.assertEqual(out.stderr.strip(), "",
                             f"{platform} scanner wrote to stderr, which corrupts "
                             f"merged json output: {out.stderr[-300:]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
