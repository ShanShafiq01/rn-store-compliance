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
        """mahalkum: plists put <key> and <true/> on separate lines, so the
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
        """carecortex/jp-mobile/mahalkum all use space-separated Groovy DSL;
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
        """jp-mobile/carecortex keep Fastfile at android/fastlane/, which was
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
              'export const cfg = { mapsKey: "AIzaSyC1234567890abcdefghijklmnopqrstuv" };')
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
        """PlinkHealth: every CRASH-PII hit was a bare event name or a count."""
        write(self.proj, "src/analytics.ts", """
export function track() {
  logEvent({ name: 'onboarding_finished' });
  logEvent({ name: 'sign_in', params: { method: 'biometric' } });
}
""")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "CRASH-PII"))


    def test_analytics_event_with_no_pii_is_not_flagged_android(self):
        """Same PlinkHealth false positive, Android scanner."""
        write(self.proj, "src/analytics.ts",
              "logEvent({ name: 'onboarding_finished' });")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "CRASH-PII"))

    def test_real_pii_in_analytics_still_flagged(self):
        """Guard: the narrowed regex must still catch actual PII."""
        write(self.proj, "src/bad.ts",
              "logEvent({ name: 'signup', params: { email: user.email } });")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "CRASH-PII"), "HIGH")

    def test_att_not_required_when_ad_id_collection_disabled(self):
        """PlinkHealth deliberately does not link AdSupport and disables ad-id
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
        """mahalkum: UIWebView in FBSDK pods = ITMS-90809, rejected since
        Dec 2020. Pods/ is in SKIP_DIRS so it was invisible."""
        write(self.proj, "ios/Pods/FBSDKCoreKit/FBSDKWebDialogView.m",
              "@interface FBSDKWebDialogView : UIView <UIWebViewDelegate>\n@end")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj), "UIWEBVIEW"), "BLOCKER")

    def test_empty_cfbundleiconname_is_blocker(self):
        """jp-mobile ships this today: ITMS-90713."""
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
        """mahalkum is armeabi-v7a + x86 only. Play has required 64-bit
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
        """jp-mobile and mahalkum both commit one. Password + keystore in the
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
        """carecortex: Podfile says `platform :ios, min_ios_version_supported`,
        which has no digits, so the regex silently parsed nothing. The real
        value lives in the pbxproj."""
        write(self.proj, "ios/Podfile", "platform :ios, min_ios_version_supported\n")
        write(self.proj, "ios/App.xcodeproj/project.pbxproj",
              "buildSettings = {\n\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 12.4;\n};")
        self.assertIsNotNone(sev(run_scan(IOS_SCAN, self.proj), "DEPLOYMENT-TARGET-OLD"))

    def test_commented_podfile_platform_is_ignored(self):
        """mahalkum's Podfile has `# platform :ios, '9.0'` commented out; the
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
        """mahalkum ships 8.0. No currently shippable Xcode can build that,
        so it is not the same finding as 12.4."""
        write(self.proj, "ios/App.xcodeproj/project.pbxproj",
              "buildSettings = {\n\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 8.0;\n};")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "DEPLOYMENT-TARGET-OLD"), "BLOCKER")

    def test_privacy_manifest_with_empty_collected_types_is_flagged(self):
        """PlinkHealth declares an empty NSPrivacyCollectedDataTypes while
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
        """mahalkum is on AGP 2.2.3, which predates App Bundles entirely.
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
