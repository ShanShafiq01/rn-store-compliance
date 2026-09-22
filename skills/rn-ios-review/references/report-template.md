# Report Template

Use this structure. Order findings by severity, not by file. Keep each finding to four lines — the reader is triaging, not reading prose.

---

# App Store Review Audit — <App Name>

**Scope:** <repo/branch, or "described only">
**Profile:** Expo managed / prebuild / bare · payments: y/n · accounts: y/n · UGC: y/n · health data: y/n · ads or analytics: y/n · OTA: y/n
**Guidelines:** Apple App Store Review Guidelines (<version date>)
**Date:** <date>

## Verdict

<One paragraph: can this ship? What's the shortest path to a submittable build? Give the count per severity.>

| Severity | Count |
|---|---|
| Blocker | n |
| High | n |
| Medium | n |
| Low | n |

## Blockers

### B1 — <Short title>
**Guideline:** 3.1.1 In-App Purchase
**Evidence:** `src/screens/Paywall.tsx:47`
**Why it rejects:** <one or two sentences>
**Fix:** <concrete change, naming the package or API>

<repeat>

## High

<same four-line shape>

## Medium

<same>

## Low

<same>

## App Store Connect items (outside the code)

- App Privacy answers — must match the SDK inventory and `PrivacyInfo.xcprivacy`
- Age rating questionnaire
- Review notes: demo account, workflow explanation, regulatory status
- Screenshots showing the app in actual use
- Privacy policy and support URLs — confirm both resolve
- <app-specific: HealthKit justification, background mode rationale, entitlement requests>

## Not verified

<Anything not confirmable from the repo — server behavior, App Store Connect settings, moderation processes, policy documents. Being explicit here is what makes the rest of the report trustworthy.>
