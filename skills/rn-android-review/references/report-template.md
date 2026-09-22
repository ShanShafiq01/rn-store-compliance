# Report Template

Use this structure. Order findings by severity, not by file. Keep each finding to four lines — the reader is triaging, not reading prose.

Keep **upload-time blockers** visually separate from policy findings: they hit different people (build engineer vs product/legal) on different timelines.

---

# Play Store Review Audit — <App Name>

**Scope:** <repo/branch, or "described only">
**Profile:** Expo managed / prebuild / bare · payments: y/n · accounts: y/n · UGC: y/n · health data: y/n · ads or analytics: y/n · background work: y/n
**Policies:** Google Play Developer Program Policy + Play Console requirements (<date checked>)
**Date:** <date>

## Verdict

<One paragraph: can this upload? Can it survive post-publication enforcement? What's the shortest path to a submittable AAB? Give the count per severity.>

| Severity | Count |
|---|---|
| Blocker | n |
| High | n |
| Medium | n |
| Low | n |

## Upload gates (fix these first — no human review involved)

| Gate | Current | Required | Status |
|---|---|---|---|
| `targetSdkVersion` | 35 | 36 | ❌ |
| Play Billing Library | 7.x | 8+ | ❌ |
| Build format | AAB | AAB | ✅ |
| 16 KB `.so` alignment | 2 unaligned | all aligned | ❌ |
| Version code | incremented | incremented | ✅ |

<Name the specific unaligned libraries — that's the long-lead item.>

## Blockers

### B1 — <Short title>
**Policy:** Play Payments
**Evidence:** `src/screens/Paywall.tsx:47`
**Why it fails:** <one or two sentences>
**Fix:** <concrete change, naming the package or API>

<repeat>

## High

<same four-line shape>

## Medium

<same>

## Low

<same>

## Merged manifest

<Permissions present in the merged manifest but not in the source manifest, with the library that contributed each. This section is the one thing a source-only review always misses.>

| Permission | Contributed by | Needed? | Action |
|---|---|---|---|
| `QUERY_ALL_PACKAGES` | <library> | no | `tools:node="remove"` |

## Play Console items (outside the code)

- Data safety form — must match the SDK inventory
- Account deletion URL (public web endpoint)
- Permission declarations: background location, photo/video, `QUERY_ALL_PACKAGES`, SMS, accessibility
- Foreground service type justifications
- Content rating questionnaire
- Ads declaration
- Families self-certification, if child-directed or mixed audience
- <app-specific: Health Connect use case, financial services declaration>

## iOS divergences

<If the app also ships to iOS, name the points where the two stores require different behavior — see `references/ios-android-divergences.md`. Skip if Android-only.>

## Not verified

<Anything not confirmable from the repo — server behavior, Console settings, moderation processes, policy documents, the merged manifest if the project wasn't built. Being explicit here is what makes the rest of the report trustworthy.>
