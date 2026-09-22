---
description: Audit a React Native / Expo app against Apple's App Store Review Guidelines
argument-hint: "[path to project root, defaults to cwd]"
---

Run a full App Store review audit on the React Native / Expo project at `$1` (default: the current working directory).

Use the `rn-ios-review` skill. Work through its four phases in order:

1. **Profile** the app using the table in the skill — Expo vs bare, payments, accounts, UGC, health data, ads/analytics, WebView, OTA. Don't skip this; it decides which rule files apply.
2. **Scan** with `python3 skills/rn-ios-review/scripts/scan.py <path>` and treat the output as leads, not verdicts.
3. **Review** against only the rule files the profile flagged, confirming every scanner hit by reading the code around it.
4. **Report** using `references/report-template.md`, ordered by severity.

For every finding give: guideline number, `file:line` evidence, why it rejects, and the concrete fix. Skip findings you can't evidence — list them under "Not verified" instead.
