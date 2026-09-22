# Apple Section 1 — Safety

Apple's most human-judgment-heavy section. Rejections here usually cite a missing *mechanism* (no way to report, no way to block) rather than bad content, which is good news: mechanisms are visible in code.

## 1.1 Objectionable content

1.1.1–1.1.7 cover defamatory, discriminatory, realistic violence, illegal-activity encouragement, false diagnostics, false information, and impersonation of Apple/others.

**RN patterns to check**
- Hardcoded sample/demo content in `mocks/`, `fixtures/`, seed data — placeholder content with slurs or lorem-ipsum violence ships to review.
- AI/LLM features with no output filter. If the app calls a model API and renders raw output, Apple expects a content filter and a report path (4.7 also applies).
- "Prank" or fake-alert features (fake virus warnings, fake calls) — 1.1.4/1.1.6.

**Fix**: Filter model output server-side; add a report control on every AI-generated surface; strip demo content from release builds.

## 1.2 User-generated content

Any app with posts, comments, chat, profile photos, uploads, or live audio/video needs **all four**.

The 6 February 2026 update clarified that **apps with random or anonymous chat are subject to 1.2**. If the app pairs strangers — Omegle-style matching, anonymous Q&A, random voice or video rooms — it carries the full UGC obligation even though nothing is persisted. RN apps built on a matching service often assume ephemerality exempts them; it doesn't.

1. A method to filter objectionable material before it appears
2. A mechanism to report offensive content, with timely response
3. The ability to block abusive users
4. Published contact information so users can reach the developer

Creator content (livestream, marketplaces) additionally needs a documented moderation and takedown plan.

**RN evidence to look for**
```ts
// Present? If not → HIGH
onReportPress={() => reportContent(postId, reason)}
blockUser(userId)
<FlatList data={posts} />          // rendering UGC with no report affordance nearby
```
Search terms: `report`, `block`, `mute`, `flag`, `moderat`, `abuse`. Absence across the whole repo in an app with a feed is a HIGH finding.

**Common miss**: report exists on posts but not on profile photos, display names, or DMs. Apple tests the path a real abuser would take.

**Fix**: Add report + block on every UGC surface, a server-side moderation queue, an EULA with a zero-tolerance clause (Apple explicitly expects this for UGC apps), and support contact in-app.

## 1.3 Kids Category

If the app targets under-13s or lands in the Kids Category:

- No third-party analytics or third-party advertising, period. Contextual ads only, human-reviewed.
- No links out, no purchases, no other distractions outside a **parental gate**.
- Must comply with COPPA, GDPR-K and similar.

**RN red flags**
```ts
import analytics from '@react-native-firebase/analytics';  // 🔴 in a Kids app
import { AppLovinMAX } from 'react-native-applovin-max';   // 🔴
Linking.openURL('https://example.com');                    // 🔴 without a gate
```
A parental gate must be a real cognitive barrier (math problem, hold-to-confirm), not a "Are you 13?" tap.

## 1.4 Physical harm

- 1.4.1 Medical apps with inaccurate data or that could cause harm need extra scrutiny; dosage calculators must come from the manufacturer, a hospital, university, health insurer, FDA-approved body, or equivalent. Disclose data sources and methodology.
- 1.4.2 Drug dosage calculators — same sourcing requirement.
- 1.4.1 **Sensor-only measurement is prohibited.** An app may not claim to measure X-rays, blood pressure, body temperature, blood glucose, or blood oxygen **using only device sensors**. Readings must come from a cleared external device. This is the most mechanically checkable health rejection there is — grep for these metrics alongside camera/flash or accelerometer access.
- 1.4.3 No facilitation of illegal drugs, tobacco, or excessive alcohol use.
- 1.4.4 DUI checkpoints may only be displayed if published by law enforcement; never encourage drunk driving or reckless behaviour such as excessive speed.
- 1.4.5 Apps must not urge users into activities (bets, challenges) or device use that risks physical harm — including unsafe use while driving.

If the app is health-related at all, read `health-and-regulated.md` — it goes deeper on both stores.

## 1.5 Developer information

Working support URL and contact means. A dead `mailto:` or a 404 support link is a real rejection cause and takes 30 seconds to verify.

## 1.6 Data security

Apps must implement appropriate security measures for user data.

**RN specifics**
```ts
// 🔴 PII/tokens in AsyncStorage — unencrypted plaintext on disk
await AsyncStorage.setItem('authToken', token);
await AsyncStorage.setItem('patientRecord', JSON.stringify(record));

// ✅
import * as SecureStore from 'expo-secure-store';   // Expo
import Keychain from 'react-native-keychain';       // bare
```
Also flag: disabled TLS validation, custom trust managers that return true, `react-native-ssl-pinning` misconfigured to no-op, and any credential in the JS bundle.

## 1.7 Reporting criminal activity

Apps for reporting alleged criminal activity must involve local law enforcement and be available only where that partnership exists.

---

## Checklist

- [ ] No objectionable placeholder/demo content in release builds
- [ ] AI-generated content is filtered and reportable
- [ ] UGC: filter, report, block, and published contact info all present and reachable from every UGC surface
- [ ] UGC EULA with zero-tolerance clause
- [ ] Kids app: no 3P analytics/ads, parental gate before links and purchases
- [ ] Medical/dosage content has a disclosed, qualified source
- [ ] Support URL resolves; contact method works
- [ ] Tokens and PII in Keychain/SecureStore, not AsyncStorage
- [ ] No credentials in the JS bundle or `app.config`
