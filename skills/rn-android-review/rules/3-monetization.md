# Google Play — Payments, Subscriptions, Ads

## Play Billing requirement

Digital goods and services consumed in the app must use **Google Play Billing**: in-app features, subscriptions, digital content, virtual currency, and app functionality unlocks.

**Exempt** (must *not* use Play Billing): physical goods, real-world services (ride-hailing, food delivery, clinical appointments), peer-to-peer payments, donations to registered nonprofits, and one-off charges for consumption outside the app.

```ts
// 🔴 BLOCKER — external checkout for digital goods on Android
Linking.openURL('https://checkout.example.com/pro');

// ✅
import { requestSubscription } from 'react-native-iap';
import Purchases from 'react-native-purchases';  // RevenueCat wraps both stores
```

### Alternative and user-choice billing

Unlike Apple, Google permits alternative billing in several jurisdictions (EEA user-choice billing, developer-program variants, and regional regulatory outcomes), each with its own fee treatment, disclosure UI, and API. If the app uses alternative billing, verify the implementation matches the program it enrolled in — a half-implemented user-choice flow is worse than not having one.

Because of this divergence, **the Android and iOS checkout paths legitimately differ.** Audit both `Platform.OS` branches against their own store's rule rather than trying to make them identical.

### Billing Library version floor

Play enforces a rolling deprecation: each major version of the Play Billing Library has roughly a two-year life, after which **new apps and updates using it are rejected at upload**. As of the 31 August 2026 step, that floor is **Billing Library 8+** (extension route to 1 November 2026 via Play Console).

```bash
# find the effective version
grep -rn "billingclient\|com.android.billingclient" android/ node_modules/react-native-iap/android/build.gradle 2>/dev/null
grep -rn "play.billingclient.version" android/app/src/main/AndroidManifest.xml
```
The version is set by your RN billing wrapper, not by your own gradle file — an old `react-native-iap` or `react-native-purchases` pins an old billing library. Upgrading the wrapper is the actual fix. Verify the current floor against the live deprecation page before calling it a blocker; the schedule advances every August.

### Subscription requirements

- Clear disclosure of price, billing period, and renewal before purchase
- Free trial and introductory terms stated unambiguously
- Cancellation instructions accessible; don't obstruct cancellation
- Restore/entitlement sync across devices, verified server-side

```ts
// 🔴 client-trusted entitlement
if (await AsyncStorage.getItem('pro')) unlock();
// ✅ verify the purchase token with Google Play Developer API server-side
```

## Ads policy

- Ads must not be deceptive, must be distinguishable from content, and must not interfere with usability
- No full-screen interstitial that can't be dismissed, and none at app open in a way that traps the user
- Rewarded ads need explicit opt-in
- Ads in child-directed apps must use Play-certified SDKs and no personalized targeting
- Ad SDK data collection must appear in the Data safety form
- On iOS the same SDK triggers ATT — an ads integration is always a two-store finding

## Real-money gambling, games, and contests

Requires Play Console approval per market, licensing, age gating, and geographic restriction by actual location. Free-to-play loot mechanics must disclose odds.

## Subscriptions / IAP mismatch between stores

One SKU catalogue, two stores, two entitlement systems. Check that:
- product IDs exist in both consoles for every paid feature
- the entitlement service treats an Apple receipt and a Play purchase token as equivalent
- restoring on one platform doesn't silently grant nothing on the other

---

## Checklist

- [ ] Digital goods use Play Billing; physical/real-world services do not
- [ ] Android checkout path never opens an external payment page for digital goods (unless enrolled in a permitted alternative-billing program, fully implemented)
- [ ] Play Billing Library at or above the current enforced major version (verify against the live deprecation page)
- [ ] Billing wrapper (`react-native-iap` / `react-native-purchases`) upgraded to a release that pins a supported billing library
- [ ] Purchases verified server-side via the Play Developer API, not a local flag
- [ ] Subscription price, period, trial, and renewal disclosed before purchase
- [ ] Cancellation is discoverable and unobstructed
- [ ] Ads dismissible, distinguishable, non-deceptive; no trap interstitials
- [ ] Rewarded ads opt-in; child-directed traffic uses certified SDKs without personalization
- [ ] Ad and analytics SDKs reflected in Data safety and in ATT on iOS
- [ ] Gambling features licensed, geo-restricted by real location, and Console-approved
- [ ] Product IDs and entitlements consistent across both stores
