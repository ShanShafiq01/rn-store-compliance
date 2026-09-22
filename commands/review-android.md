---
description: Audit a React Native / Expo app against Google Play's Developer Program Policies
argument-hint: "[path to project root, defaults to cwd]"
---

Run a full Play Store policy audit on the React Native / Expo project at `$1` (default: the current working directory).

Use the `rn-android-review` skill. Work through its four phases in order:

1. **Profile** the app using the table in the skill — Expo vs bare, payments, accounts, UGC, health data, ads/analytics, background work, native `.so` dependencies.
2. **Scan** with `python3 skills/rn-android-review/scripts/scan.py <path>`. Report the upload-time gates first — target API level, Play Billing version, AAB, 16 KB alignment — since those block the release with no human review involved.
3. **Review** against only the rule files the profile flagged, confirming every scanner hit by reading the code around it.
4. **Report** using `references/report-template.md`, ordered by severity, with upload gates in their own table.

The scanner reads the source manifest. If the project has been built, also check `android/**/merged_manifests/**/AndroidManifest.xml` and attribute each extra permission to the library that contributed it.

For every finding give: policy name, `file:line` evidence (or the Console artifact), why it fails, and the concrete fix. Skip findings you can't evidence — list them under "Not verified" instead.
