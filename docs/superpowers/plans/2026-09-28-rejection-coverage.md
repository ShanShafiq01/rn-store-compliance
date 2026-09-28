# Rejection-Driven Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap exposed by a real App Store rejection letter for a health app, then work outward to full Apple/Play guideline coverage.

**Architecture:** Each gap gets a rule-file section (what Claude reasons from) and, where the condition is statically visible in an RN tree, a scanner check pinned by a regression test. Rejection letters are the highest-quality input this tool can get — a real reviewer already decided the rule applies, so these go first and in full before any speculative coverage.

**Tech Stack:** Python 3.8+ stdlib only, unittest, Markdown rule files.

**Spec:** This plan's source is the rejection letter pasted in-session on 2026-09-28 plus `docs/superpowers/specs/` policy-coverage audit findings recorded in CHANGELOG 3.0.0.

## Global Constraints

- Scanners stay Python 3.8+, stdlib only, read-only, no network, no writes. Never add a dependency.
- Every new check needs BOTH a dirty-fixture assertion and a clean-fixture silence assertion.
- Run `python3 scripts/gen_checks.py` after ANY check change; CI fails on drift.
- Guideline numbers are verified against the live guidelines before being written, never from memory.
- A new check ID must not duplicate an existing one in `docs/CHECKS.md`.
- Findings are leads, not verdicts: description text says what to confirm, never asserts a violation the scanner cannot see.

## Review Focus

Five conditions these tasks imply but whose tests must be written deliberately:

1. **A compliant app must stay silent.** Every check below fires on absence (no disclaimer, no citation). Absence checks are the easiest to make noisy — each needs a clean-fixture test proving a compliant app produces nothing.
2. **Non-health apps must not see health findings.** The medical checks must gate on health signals, or they fire on all 34 fleet projects.
3. **Permission-vs-usage must not false-positive on indirect use.** A Health Connect permission used via a wrapper or a constant list is still used; matching only literal permission strings in JS will mis-report.
4. **Guideline citations in new rules must be live-verified.** Task 0 exists solely because this plan was written after finding our own 3.1.5 reference wrong.
5. **Scanner output must not leak the medical content it inspects.** Existing tests assert credentials are never printed; medical text deserves the same.

---

## Scope note — this plan is Phase 1 of four

"Cover all Apple and Play guidelines" is not one plan. Measured against the live rulebooks, the current files map onto roughly **5 of Play's 14 top-level policy families**, and Apple §2.5.9–2.5.18 plus §5.2/5.3/5.6 are thin. Splitting:

- **Phase 1 (this plan)** — the 7 verified rejection points. Every one is a rule a real reviewer has already enforced against a real app.
- **Phase 2** — Apple's weakest sections: 2.5.9, 2.5.11–2.5.16, 2.5.18 (the entire iOS ads rule set is absent), 2.4.4, 5.1.2(iii)–(vi), 5.2, 5.3, 5.6.
- **Phase 3** — Play's nine missing policy families: Malware, MUwS, Use of SDKs, Store Listing and Promotion, Blockchain Content, Other Programs (Wear/TV/Auto), Enforcement, plus the 2025–26 policy changes with 27 Jan 2027 deadlines.
- **Phase 4** — Console/metadata gates that no static scanner can see: EU DSA trader status, Play app-package registration, organization-account requirements for health and finance.

Phases 2–4 get their own plans. Do not start them from this document.

---

### Task 0: Verify every guideline number this plan will cite

**Files:**
- Modify: none yet — this task produces a verified reference list used by Tasks 1–7.

**Interfaces:**
- Produces: a verified mapping `{topic: guideline_number}` consumed by every later task's rule-file edit.

- [ ] **Step 1: Fetch the live guidelines and record the exact numbers**

Fetch `https://developer.apple.com/app-store/review/guidelines/` and record, verbatim, the heading of each of: 1.4.1, 2.1, 3.1.3(e), 4.8, 5.1.3. Confirm whether 3.1.5 is Cryptocurrencies.

Known as of 2026-09-28, re-confirm before use:
- `3.1.3(e)` — Goods and Services Outside of the App (NOT 3.1.5(a); that number is stale)
- `3.1.5` — Cryptocurrencies
- `4.8` — Login Services
- `1.4.1` — Physical Harm

- [ ] **Step 2: Record them in the plan's task notes**

Write the confirmed numbers into a scratch note. Any number that cannot be confirmed does not get written into a rule file — the rule is written without a citation instead.

- [ ] **Step 3: Commit nothing**

This task produces knowledge, not a diff. Proceed to Task 1.

---

### Task 1: Sign in with Apple — do not re-ask for name or email

**Files:**
- Modify: `skills/rn-ios-review/rules/4-design.md` (the 4.8 Login Services section)
- Modify: `skills/rn-ios-review/scripts/scan.py` (add rule to `RULES`)
- Test: `tests/test_scanners.py`

**Interfaces:**
- Produces: check ID `SIWA-REDUNDANT-PROFILE`, severity HIGH, guideline `4.8`.

- [ ] **Step 1: Write the failing test**

```python
class TestRejectionDrivenChecks(ScannerTestBase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(dir=self.tmp)
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@invertase/react-native-apple-authentication":"2.3.0"}}')

    def test_profile_completion_after_apple_signin_is_flagged(self):
        """Real rejection: 'users are required to provide their name and/or
        email address after using Sign in with Apple even though that
        information is already provided by the Authentication Services
        framework.'"""
        write(self.proj, "src/auth/AppleSignIn.tsx", """
import { appleAuth } from '@invertase/react-native-apple-authentication';
export async function signIn() {
  const res = await appleAuth.performRequest();
  navigation.navigate('CompleteProfile');
}
""")
        write(self.proj, "src/auth/CompleteProfile.tsx", """
export function CompleteProfile() {
  return (<><TextInput placeholder="Full name" /><TextInput placeholder="Email" /></>);
}
""")
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
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj),
                              "SIWA-REDUNDANT-PROFILE"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: FAIL — `None != 'HIGH'`, because no such check exists.

- [ ] **Step 3: Implement in `scan_structural`**

This is an absence/co-occurrence condition, so it is a structural finding, not a `RULES` tuple. Add near the other `_grep`-based structural checks:

```python
    # Sign in with Apple must not re-ask for what the token already carries.
    if _grep(root, r"@invertase/react-native-apple-authentication|"
                   r"expo-apple-authentication|appleAuth\.performRequest") \
            and _grep(root, r"(?i)(CompleteProfile|complete[-_]?profile|"
                            r"ProfileSetup|onboarding/name)"):
        findings.append({
            "id": "SIWA-REDUNDANT-PROFILE", "severity": "HIGH", "guideline": "4.8",
            "description": "Sign in with Apple is present alongside a profile-completion "
                           "screen. Apple rejects apps that ask for a name or email the "
                           "Authentication Services framework already returned — read "
                           "fullName and email from the first authorization response and "
                           "pre-fill. Note both are returned ONLY on first authorization, "
                           "so persist them then; a returning user yields null and must "
                           "not be re-prompted.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: PASS, both tests.

- [ ] **Step 5: Add the rule-file section**

In `skills/rn-ios-review/rules/4-design.md`, under the 4.8 section, add:

```markdown
### 4.8 — the design requirements, not just the presence of the button

Offering Sign in with Apple is necessary but not sufficient. A real rejection:

> "users are required to provide their name and/or email address after using
> Sign in with Apple even though that information is already provided by the
> Authentication Services framework."

The RN trap: `fullName` and `email` are returned **only on the first
authorization**. Every later sign-in returns null for both, so teams add a
"complete your profile" screen, which is what gets cited.

```ts
// 🔴 discards the name, then asks for it
const res = await appleAuth.performRequest();
navigation.navigate('CompleteProfile');

// ✅ persist on first authorization; never re-prompt
const res = await appleAuth.performRequest();
if (res.fullName?.givenName) await api.post('/profile', { name: res.fullName });
```

If existing accounts have empty names because an earlier build discarded them,
backfill by migration — do not prompt.
```

- [ ] **Step 6: Regenerate docs and commit**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py
git add -A && git commit -m "Add SIWA-REDUNDANT-PROFILE (4.8 design requirements)"
```

---

### Task 2: Medical citations and medical disclaimer (1.4.1)

**Files:**
- Modify: `skills/rn-ios-review/rules/1-safety.md`
- Modify: `skills/rn-ios-review/rules/health-and-regulated.md`
- Modify: `skills/rn-ios-review/scripts/scan.py`
- Test: `tests/test_scanners.py`

**Interfaces:**
- Produces: `MEDICAL-NO-DISCLAIMER` (HIGH, 1.4.1), `MEDICAL-NO-CITATION` (MEDIUM, 1.4.1), `SENSOR-ONLY-VITALS` (BLOCKER, 1.4.1).
- Produces: `_is_health_app(root)` in `skills/rn-ios-review/scripts/scan.py`. It is iOS-only — Task 5 works in the Android scanner and gates on declared Health Connect permissions instead, so it does NOT call this helper. Do not try to share it across the two files; the scanners are deliberately independent.

- [ ] **Step 1: Write the failing tests**

```python
    def test_health_app_without_disclaimer_is_flagged(self):
        """Real rejection: 'The app provides medical diagnoses or treatment
        advice but does not include the required medical disclaimer.'"""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/Insights.tsx",
              "export const advice = 'Your cholesterol suggests you should start statins.';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "MEDICAL-NO-DISCLAIMER"), "HIGH")

    def test_health_app_with_disclaimer_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0",'
              '"@kingstinct/react-native-healthkit":"13.0.0"}}')
        write(self.proj, "src/Disclaimer.tsx",
              "export const TEXT = 'This app does not provide medical advice. "
              "Always consult your physician before making medical decisions.';")
        self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), "MEDICAL-NO-DISCLAIMER"))

    def test_non_health_app_never_sees_medical_findings(self):
        """Guard: without health signals these must never fire — otherwise they
        fire on every project in a fleet."""
        write(self.proj, "package.json", '{"dependencies":{"react-native":"0.76.0"}}')
        write(self.proj, "src/Shop.tsx", "export const x = 1;")
        for check in ("MEDICAL-NO-DISCLAIMER", "MEDICAL-NO-CITATION", "SENSOR-ONLY-VITALS"):
            self.assertIsNone(sev(run_scan(IOS_SCAN, self.proj), check), check)

    def test_sensor_only_vitals_claim_is_blocker(self):
        """1.4.1 bans claiming to measure blood pressure, glucose, blood oxygen,
        body temperature or take x-rays using only device sensors."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-vision-camera":"4.0.0"}}')
        write(self.proj, "src/BP.tsx",
              "export const title = 'Measure your blood pressure with your camera';")
        self.assertEqual(sev(run_scan(IOS_SCAN, self.proj),
                             "SENSOR-ONLY-VITALS"), "BLOCKER")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: FAIL on all four new tests.

- [ ] **Step 3: Implement the health gate and the three checks**

```python
HEALTH_SDKS = re.compile(
    r"react-native-healthkit|react-native-health\b|react-native-health-connect|"
    r"@kingstinct/react-native-healthkit|fhir|expo-health", re.I)
MEDICAL_ADVICE = re.compile(
    r"(?i)\b(diagnos|treatment|prescrib|statin|dosage|mg/dL|"
    r"blood pressure|cholesterol|symptom)\w*\b")
DISCLAIMER = re.compile(
    r"(?i)(not (a substitute for|intended as) (professional )?medical advice|"
    r"consult (your|a) (physician|doctor|healthcare)|"
    r"does not (provide|constitute) medical advice)")
SENSOR_ONLY = re.compile(
    r"(?i)(measure|check|scan|read)\w*[^\n]{0,40}"
    r"(blood pressure|blood glucose|blood oxygen|body temperature|x-?ray)")


def _is_health_app(root):
    return bool(_grep(root, HEALTH_SDKS.pattern) or
                _grep(root, r"(?i)\b(patient|clinical|vitals|biomarker)\b"))
```

In `scan_structural`, after the health gate:

```python
    if _is_health_app(root):
        if _grep(root, MEDICAL_ADVICE.pattern) and not _grep(root, DISCLAIMER.pattern):
            findings.append({
                "id": "MEDICAL-NO-DISCLAIMER", "severity": "HIGH", "guideline": "1.4.1",
                "description": "Health app surfaces medical language with no disclaimer "
                               "found. 1.4.1 requires a reminder to consult a doctor before "
                               "making medical decisions, and Apple checks the App Store "
                               "DESCRIPTION as well as the app — a rejection here is often "
                               "fixed in metadata, not code.",
                "file": "(repo-wide)", "line": 0, "evidence": "",
            })
        if _grep(root, MEDICAL_ADVICE.pattern) and not _grep(
                root, r"(?i)(pubmed|doi\.org|nih\.gov|citation|\bsource[sd]?\b:)"):
            findings.append({
                "id": "MEDICAL-NO-CITATION", "severity": "MEDIUM", "guideline": "1.4.1",
                "description": "Health or medical information with no citations found. "
                               "1.4.1 requires sources for medical claims, easy for the user "
                               "to find — link each recommendation to its source.",
                "file": "(repo-wide)", "line": 0, "evidence": "",
            })
        if _grep(root, SENSOR_ONLY.pattern) and _grep(
                root, r"react-native-vision-camera|expo-camera|Accelerometer"):
            findings.append({
                "id": "SENSOR-ONLY-VITALS", "severity": "BLOCKER", "guideline": "1.4.1",
                "description": "Possible claim to measure a vital sign using only device "
                               "sensors. 1.4.1 explicitly bans apps claiming to take x-rays "
                               "or measure blood pressure, body temperature, blood glucose "
                               "or blood oxygen with device sensors alone. Readings must "
                               "come from a cleared external device.",
                "file": "(repo-wide)", "line": 0, "evidence": "",
            })
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 tests/test_scanners.py -v`
Expected: PASS, all tests including the pre-existing 69.

- [ ] **Step 5: Add the rule-file sections**

In `skills/rn-ios-review/rules/1-safety.md`, replace the 1.4.1 bullet with the full rule: sourcing requirement, the sensor-only ban quoted verbatim, the doctor-disclaimer requirement, and the note that the disclaimer is checked in the App Store description. Cross-reference `health-and-regulated.md`.

- [ ] **Step 6: Regenerate docs and commit**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py
git add -A && git commit -m "Add 1.4.1 medical disclaimer, citation and sensor-only checks"
```

---

### Task 3: Guideline 2.1 — what App Review asks a health app for

**Files:**
- Modify: `skills/rn-ios-review/rules/2-performance.md`
- Modify: `skills/rn-ios-review/references/report-template.md`

No scanner check: this is entirely about what goes in App Review Notes, which no static analysis can see.

- [ ] **Step 1: Add the 2.1 section**

```markdown
### 2.1 — Information Needed, for apps that process documents or run AI

A real 2.1 hold on a health app asked, verbatim:

> - Please provide test lab result uploaded in the app
> - Please explain what happens after Lab result is uploaded? How does app reads
>   report? Please specify background process?
> - Please specify all health results that are produced using AI?

None of that is visible in a build, so it is never found by review — it is
found by the reviewer asking, which costs a review cycle. Pre-empt it in App
Review Notes whenever the app ingests a document or generates output with a
model:

- **A sample input.** Attach an actual lab PDF or equivalent, plus screenshots
  of the result screen. A reviewer who cannot produce a result will hold.
- **The pipeline, named.** Where the file goes, what redacts PHI, which model
  analyses it, where output is stored. "S3 → redaction → Bedrock → result" is
  the shape they want, not a paragraph about architecture.
- **An explicit inventory of AI-generated output.** Every surface where a model
  produced what the user reads. Apple asks this directly now.
- **Consent and retention** for anything uploaded.

If the app is gated, the demo account must reach all of it. Where a demo
account is impossible for legal reasons, 2.1 permits a built-in demo mode
**with prior Apple approval** — which is often the right answer for clinical
apps, and needs requesting before submission, not during.
```

- [ ] **Step 2: Add a Review Notes block to the report template**

Add a "What to put in App Review Notes" section so every generated audit of a
health or AI app emits the list above pre-filled.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "Add 2.1 review-notes guidance for document and AI pipelines"
```

---

### Task 4: 3.1.3(e) physical goods, and the word "subscription"

**Files:**
- Modify: `skills/rn-ios-review/rules/3-business.md`
- Modify: `skills/rn-ios-review/scripts/scan.py`
- Test: `tests/test_scanners.py`

**Interfaces:**
- Produces: `SUBSCRIPTION-COPY-MISMATCH` (MEDIUM, 3.1.3(e)).

- [ ] **Step 1: Write the failing test**

```python
    def test_subscription_wording_without_iap_is_flagged(self):
        """A real 2.1(b) hold was caused by in-app copy calling one-time
        purchases 'subscriptions' while no IAP products existed."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","@stripe/stripe-react-native":"0.38.0"}}')
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: FAIL — check does not exist.

- [ ] **Step 3: Implement in `scan_structural`**

```python
    # Copy that says "subscription" with no IAP in the tree invites a 2.1(b)
    # hold: the reviewer looks for subscription products and finds none.
    if _grep(root, r"(?i)\bsubscriptions?\b") and not _grep(
            root, r"react-native-iap|react-native-purchases|expo-in-app-purchases"):
        findings.append({
            "id": "SUBSCRIPTION-COPY-MISMATCH", "severity": "MEDIUM",
            "guideline": "3.1.1 / 3.1.3(e)",
            "description": "In-app copy says 'subscription' but no IAP library is present. "
                           "If these are one-time purchases, or physical goods and services "
                           "consumed outside the app under 3.1.3(e), the word invites a "
                           "2.1(b) hold — the reviewer looks for subscription products and "
                           "finds none. Say what it is: a one-time purchase, a program fee, "
                           "or a real auto-renewing subscription that must then use StoreKit.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/test_scanners.py -v`
Expected: PASS.

- [ ] **Step 5: Correct and extend the 3.1.3 section**

In `3-business.md`, under the 3.1.3 sub-letter list already added in 3.0.0, expand **(e)**:

```markdown
**3.1.3(e) Goods and Services Outside of the App.** Physical goods, and services
consumed outside the app, must NOT use IAP — they use another payment method.
This is the reciprocal of 3.1.1, and teams get cited in both directions.

Note the number: physical goods are **3.1.3(e)**. The older citation 3.1.5(a) is
stale — 3.1.5 is now Cryptocurrencies. A response to App Review quoting the wrong
number invites a second round.

A mixed bundle is the hard case: a program fee covering both an in-app feature
and a shipped lab kit. Apple looks at what the user is actually buying. If the
digital part can be bought alone, it needs IAP.
```

- [ ] **Step 6: Regenerate docs and commit**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py
git add -A && git commit -m "Correct 3.1.3(e) physical goods; add subscription-copy check"
```

---

### Task 5: Health Connect — permissions declared but never used

**Files:**
- Modify: `skills/rn-android-review/scripts/scan.py`
- Modify: `skills/rn-android-review/rules/health-and-regulated.md`
- Test: `tests/test_scanners.py`

**Interfaces:**
- Produces: `HEALTH-PERM-UNUSED` (HIGH, Health Connect restricted data).

- [ ] **Step 1: Write the failing test**

```python
    def test_declared_health_permission_never_read_in_code_is_flagged(self):
        """Health Connect access needs an approved use case per data type.
        Declaring a type the code never reads is an over-request."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-health-connect":"3.5.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml", """<manifest>
  <uses-permission android:name="android.permission.health.READ_STEPS"/>
  <uses-permission android:name="android.permission.health.READ_BLOOD_PRESSURE"/>
</manifest>""")
        write(self.proj, "src/health.ts",
              "export const TYPES = ['Steps'];\nreadRecords('Steps');")
        result = run_scan(ANDROID_SCAN, self.proj)
        self.assertEqual(sev(result, "HEALTH-PERM-UNUSED"), "HIGH")
        hit = [f for f in result["findings"] if f["id"] == "HEALTH-PERM-UNUSED"][0]
        self.assertIn("BloodPressure", hit["description"])
        self.assertNotIn("Steps", hit["description"])

    def test_all_health_permissions_used_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","react-native-health-connect":"3.5.0"}}')
        write(self.proj, "android/app/src/main/AndroidManifest.xml",
              '<manifest><uses-permission '
              'android:name="android.permission.health.READ_STEPS"/></manifest>')
        write(self.proj, "src/health.ts", "readRecords('Steps');")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "HEALTH-PERM-UNUSED"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Health Connect permission `READ_BLOOD_PRESSURE` maps to record type `BloodPressure`.
Convert SCREAMING_SNAKE to PascalCase and look for that token anywhere in JS/TS:

```python
def scan_health_permissions(root, findings):
    """Health Connect grants are per data type and need an approved use case.
    A declared type the code never reads is an over-request — Google reviews
    these, and an unjustified type can cost the whole Health Connect grant."""
    declared = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn != "AndroidManifest.xml":
                continue
            try:
                text = open(os.path.join(dirpath, fn), encoding="utf-8",
                            errors="ignore").read()
            except OSError:
                continue
            declared |= set(re.findall(
                r'android\.permission\.health\.(?:READ|WRITE)_([A-Z_]+)', text))
    if not declared:
        return
    unused = []
    for perm in sorted(declared):
        pascal = "".join(p.capitalize() for p in perm.split("_"))
        if not _grep(root, r"\b%s\b" % re.escape(pascal)):
            unused.append(pascal)
    if unused:
        findings.append({
            "id": "HEALTH-PERM-UNUSED", "severity": "HIGH",
            "policy": "Health Connect restricted data",
            "description": "Health Connect permissions declared with no matching read in "
                           "the code: " + ", ".join(unused) + ". Access is granted per data "
                           "type against a declared use case, so an unused type is an "
                           "over-request — it widens your Data safety disclosure, and an "
                           "unjustified type can cost the whole Health Connect grant on "
                           "review. Remove it, or use it.",
            "file": "android/app/src/main/AndroidManifest.xml", "line": 0, "evidence": "",
        })
```

Wire into `main()` after `scan_manifests`.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/test_scanners.py -v`
Expected: PASS.

- [ ] **Step 5: Add the rule-file section**

In `rn-android-review/rules/health-and-regulated.md`, document the per-type
approval model, the 5 Mar 2025 health-records tightening, and the divergence
worth recording: Play bars using health data for **employment or insurance
eligibility**, while Apple 5.1.3 permits health data to deliver a benefit such
as a reduced insurance premium when the benefit provider submits the app. Add
that divergence to `ios-android-divergences.md`.

- [ ] **Step 6: Regenerate docs and commit**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py
git add -A && git commit -m "Add HEALTH-PERM-UNUSED; document per-type Health Connect approval"
```

---

### Task 6: Play AI-generated content — in-app reporting

**Files:**
- Modify: `skills/rn-android-review/rules/1-restricted-content.md`
- Modify: `skills/rn-android-review/scripts/scan.py`
- Test: `tests/test_scanners.py`

**Interfaces:**
- Produces: `AI-CONTENT-NO-REPORT` (HIGH, AI-Generated Content policy).

- [ ] **Step 1: Write the failing test**

```python
    def test_ai_chat_without_in_app_reporting_is_flagged(self):
        """Play: apps that generate AI content must provide in-app user
        reporting or flagging of offensive content, without leaving the app."""
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","openai":"4.0.0"}}')
        write(self.proj, "src/Chat.tsx",
              "const res = await openai.chat.completions.create({ messages });")
        self.assertEqual(sev(run_scan(ANDROID_SCAN, self.proj),
                             "AI-CONTENT-NO-REPORT"), "HIGH")

    def test_ai_chat_with_reporting_is_silent(self):
        write(self.proj, "package.json",
              '{"dependencies":{"react-native":"0.76.0","openai":"4.0.0"}}')
        write(self.proj, "src/Chat.tsx",
              "const res = await openai.chat.completions.create({ messages });")
        write(self.proj, "src/Report.tsx",
              "export const reportContent = (id, reason) => api.post('/reports', { id, reason });")
        self.assertIsNone(sev(run_scan(ANDROID_SCAN, self.proj), "AI-CONTENT-NO-REPORT"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/test_scanners.py TestRejectionDrivenChecks -v`
Expected: FAIL.

- [ ] **Step 3: Implement in `scan_structural`**

```python
    # Play's AI-Generated Content policy: in-app reporting of offensive output.
    if _grep(root, r"openai|@anthropic-ai|generativelanguage|bedrock-runtime|"
                   r"@google/generative-ai|replicate|huggingface") \
            and not _grep(root, r"(?i)(reportContent|report_message|flagContent|"
                                r"reportResponse|/reports?\b)"):
        findings.append({
            "id": "AI-CONTENT-NO-REPORT", "severity": "HIGH",
            "policy": "AI-Generated Content",
            "description": "A generative model is called with no in-app reporting or "
                           "flagging path found. Play requires apps that generate AI "
                           "content to let users report or flag offensive output WITHOUT "
                           "leaving the app, and to use that feedback to improve filtering. "
                           "A support email or a web form does not satisfy it.",
            "file": "(repo-wide)", "line": 0, "evidence": "",
        })
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/test_scanners.py -v`
Expected: PASS.

- [ ] **Step 5: Add the Android rule section**

Add an AI-Generated Content section to `1-restricted-content.md` covering: the
in-app reporting requirement, the feedback-into-filtering obligation, the Play
Console AI asset self-declaration for store listing and promotional assets, and
the 15 Jul 2026 clarification that the User Data policy applies to third-party
AI integrations. Cross-reference Apple 1.2 and 4.7 so a dual-store audit lands
both.

- [ ] **Step 6: Regenerate docs and commit**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py
git add -A && git commit -m "Add AI-CONTENT-NO-REPORT and the Play AI content policy"
```

---

### Task 7: Re-run the fleet and triage

**Files:**
- Modify: whichever check misfires
- Test: `tests/test_scanners.py`

Seven absence-based checks were just added. Absence checks are the noisiest
kind, and the 3.0.0 fleet run proved that only real projects expose this.

- [ ] **Step 1: Run both scanners across all 34 projects**

The harness is not checked in. Recreate it:

```bash
OUT=$(mktemp -d)
R=$(pwd)
G=$(dirname "$R")
for d in "$G"/*/; do
  name=$(basename "$d")
  [ "$name" = "rn-store-compliance" ] && continue
  for cand in "$d" "$d/apps/mobile"; do
    [ -f "$cand/package.json" ] || continue
    grep -q '"react-native"' "$cand/package.json" 2>/dev/null || continue
    for plat in ios android; do
      timeout 600 python3 "$R/skills/rn-$plat-review/scripts/scan.py" "$cand" \
        --format json > "$OUT/${name}.${plat}.json" 2>/dev/null
    done
    break
  done
done
echo "results in $OUT"
```

- [ ] **Step 2: Count hits per new check**

Any of the seven firing on more than ~40% of projects is suspect: medical
checks should fire only on health apps, `AI-CONTENT-NO-REPORT` only where a
model SDK exists.

- [ ] **Step 3: Read one real hit per check and confirm it by hand**

For each of the seven, open the matched file and decide whether a reviewer
would agree. Record the verdict.

- [ ] **Step 4: Pin every false positive with a regression test, then fix**

Follow the existing `TestFleetFalsePositives` pattern: name the project that
exposed it in the docstring.

- [ ] **Step 5: Re-run the fleet and the suite**

```bash
python3 tests/test_scanners.py && python3 scripts/gen_checks.py --check
```

- [ ] **Step 6: Bump to 3.1.0, update CHANGELOG, commit**

Minor, not major: new checks and new rules, no changed severities or IDs on
existing checks.

```bash
git add -A && git commit -m "Triage fleet results for the rejection-driven checks; 3.1.0"
```
