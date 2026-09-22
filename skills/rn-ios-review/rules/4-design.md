# Apple Section 4 — Design

Where cross-platform apps get caught: an app built to be identical everywhere reads to Apple as a web wrapper or a template clone.

## 4.1 Copycats
Don't copy another app's name, UI, or concept. Check that app name, icon, and onboarding aren't near-duplicates of a market leader.

## 4.2 Minimum functionality

The rule that matters most for RN/Expo: an app must offer lasting value and can't simply be a repackaged website, a "song book," or a marketing brochure.

```tsx
// 🟠 MEDIUM→HIGH — thin wrapper
export default function App() {
  return <WebView source={{ uri: 'https://example.com' }} />;
}
```
**Fix direction**: add genuinely native capability — push notifications, offline caching, biometrics, camera/document capture, background sync, share-sheet integration, widgets. For a healthcare client portal, offline record access plus biometric unlock is usually enough to clear 4.2.

4.2.3(i) requires an app to work **on its own, without requiring another app to be installed** (4.2.3(ii) additionally requires disclosing download size and prompting before downloading extra resources at first launch). It is about app independence, not offline capability. 4.2.6 targets apps generated from a commercial template or app-generation service, submitted by the service rather than the client — this bites agencies shipping many similar client apps from one account. Ship each client app from the **client's own developer account**.

## 4.3 Spam

**Rewritten in the 8 June 2026 update — this is stricter than the older 4.3(a)/(b) framing most checklists still quote.**

- 4.3(a) duplicate apps: multiple near-identical binaries from one account is a rejection and can escalate to account level. An agency shipping a dozen similar client apps from one developer account should expect scrutiny.
- 4.3(b) now names **"well established" categories** — dating, flashlight, sound effects, wallpaper, simple timers, fortune telling — and states new submissions in them won't be accepted unless they offer a meaningfully different or improved experience.
- Apple states it may **remove existing apps** in those categories that aren't updated or improved, **or that don't attract customers**. Low install numbers are now a stated removal risk, which is new.
- A separate line targets "mediocre, low-quality, or low-effort" apps by name, including drinking games and novelty apps, and warns that repeated submissions of that kind can lead to removal from the **Apple Developer Program** itself.

Practical read for an agency or a side-project portfolio: a thin app in a saturated category is no longer just a rejection risk for that app, it's an account-standing risk. If the app under audit is in one of the named categories, say so explicitly in the report and describe what makes it meaningfully different — that argument belongs in the review notes too.

## 4.4 Extensions
Keyboard extensions must provide functionality without network access and must not collect user activity. Widgets and share extensions must work standalone.

## 4.5 Apple sites and services
Use Apple APIs as documented; don't scrape iTunes/App Store data; Apple Music/Maps usage per terms. Push notifications must not be used for advertising, promotions, or direct marketing without explicit user consent and an opt-out — RN apps routinely violate this with promo campaigns sent via a marketing SDK.

```ts
// 🟡 marketing pushes with no consent toggle
OneSignal.sendTag('promo_optin', 'true'); // needs an explicit, revocable opt-in
```

## 4.7 Mini apps, chatbots, game emulators
Apps that host third-party mini-apps or chatbots must have appropriate moderation, age rating, and must not allow the mini-apps to bypass IAP. AI chatbot surfaces need content filtering and reporting.

## 4.8 Login services

If the app uses a third-party or social login, it must also offer a login option that:
- limits data collection to name and email
- allows the user to keep the email private
- does not collect interactions for advertising without consent

Sign in with Apple satisfies this. Exceptions exist (apps that use only your own account system, education/enterprise apps with existing accounts).

```tsx
// 🟡 Google-only login → needs a compliant alternative
<GoogleSigninButton onPress={signInWithGoogle} />

// ✅
import * as AppleAuthentication from 'expo-apple-authentication';
```

## 4.9 Apple Pay — implement correctly, disclose what the user is buying.

## 4.10 Monetizing built-in capabilities
Don't charge for access to the camera, gyroscope, Face ID, or other built-in features, or for the Apple device's own functionality.

---

## Checklist

- [ ] App has substantive native functionality beyond a WebView
- [ ] Something useful renders with no network connection
- [ ] Name, icon, and UI aren't confusable with an existing app
- [ ] Not one of several near-identical apps from the same account
- [ ] Client apps shipped from the client's developer account, not the agency's
- [ ] Push notifications: no marketing without explicit consent + opt-out
- [ ] Social login accompanied by a privacy-preserving alternative (or a documented exception)
- [ ] Extensions function standalone and don't exfiltrate activity
- [ ] No charge for built-in device capabilities
