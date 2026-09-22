# Apple Section 3 — Business

Payment violations are the highest-cost findings: they are rejections *and* they require a product decision, not a code tweak, so surface them first.

## 3.1.1 In-App Purchase

Digital content, features, subscriptions, unlocks, and services consumed **inside** the app must use StoreKit IAP. You may not steer users to an external purchase mechanism unless you hold the relevant entitlement (External Purchase Link Entitlement / Link Entitlement, or a court-ordered regional allowance), and even then the entitlement dictates the exact UI and disclosure.

```ts
// 🔴 BLOCKER — external payment for digital goods
Linking.openURL('https://buy.stripe.com/xyz');
import { initStripe, presentPaymentSheet } from '@stripe/stripe-react-native'; // for a digital unlock
WebView({ uri: 'https://app.example.com/upgrade' });  // paywall in a WebView

// ✅ StoreKit via RN
import Purchases from 'react-native-purchases';   // RevenueCat
import { requestPurchase } from 'react-native-iap';
```

**Physical goods and real-world services are the opposite**: they must *not* use IAP (Stripe is correct for a food delivery or clinic appointment fee). Classify every SKU before judging. A telehealth consult with a human clinician is a real-world service; an AI symptom-checker subscription is digital content.

Watch for the `Platform.OS` split — a common RN shape is Stripe on Android, IAP on iOS. Verify the iOS branch never reaches the Stripe path, including deep links and WebView fallbacks.

## 3.1.2 Subscriptions

Must work across all of a user's devices, and the app must clearly present:
- title, length, and content of the subscription
- price per unit and renewal terms
- links to Terms of Use (EULA) and Privacy Policy on the paywall itself

Auto-renewing subs need a minimum 7-day period and must not lock the user out of already-purchased content.

```ts
// Paywall must render, not just link deep in settings:
<Text>$9.99/month, auto-renews until cancelled</Text>
<Link href={TERMS_URL}>Terms of Use</Link>
<Link href={PRIVACY_URL}>Privacy Policy</Link>
```
Missing terms links on the paywall is one of the most common RN paywall rejections.

## 3.1.3 Content-based "reader" apps and other exceptions

3.1.3(a) reader apps (magazines, books, audio, video, cloud storage) may let users access previously purchased content and, with the External Link Account Entitlement, link out to account management. 3.1.3(b) multiplatform services, (d) person-to-person experiences, (e) goods and services outside the app, (f) free stand-alone apps, (g) enterprise services.

If the app claims an exception, verify it holds: no in-app purchase prompt, no "sign up on our website" copy pointing at a paywall without the entitlement.

## 3.1.4 Hardware-specific content
## 3.1.5 Crypto
Wallets are permitted if offered by the developer or an enrolled organization; on-device mining is not (see 2.4.2 — mining is an unrelated background process; **cloud-based mining is permitted**); ICO/trading requires appropriate licensing.

> **3.1.6 and 3.1.7 do not exist.** Section 3.1 ends at 3.1.5. Apple Pay is **4.9**;
> ATT sits under **5.1.2**, and in-app advertising under **1.3** for Kids plus the
> display-advertising rule in §2.5 — verify that rule's current number against the
> live guidelines before citing it, as §2.5 has been renumbered. Citing a guideline
> number that does not exist gets the whole report dismissed.

## 3.1.3(d) Person-to-person services
Real-time one-to-one experiences between **two individuals** (tutoring, medical
consultation, personal training, a real-estate tour) may use payment methods other
than IAP. **One-to-few and one-to-many must use IAP.** This boundary decides the
payment architecture for most telehealth and coaching apps — a group class in the
same codebase as a 1:1 session needs a different payment path.

## 3.2.1 Acceptable business models
Approved financial institutions, insurance, and similar may operate; loan apps must not exceed 36% APR and must not require repayment in 60 days or less.

## 3.2.2 Unacceptable
- Artificially inflating rankings or reviews (also 5.6.1)
- Charging for features that use built-in device capabilities
- Binary options / gambling dressed as investment
- Apps whose primary purpose is to drive affiliate traffic

---

## Restore purchases

Non-consumable purchases and subscriptions need a visible **Restore Purchases** control. Apple rejects for its absence routinely.

```ts
// ✅
<Button title="Restore Purchases" onPress={() => Purchases.restorePurchases()} />
```

---

## Checklist

- [ ] Every SKU classified as digital (IAP required) or physical/real-world service (IAP forbidden)
- [ ] iOS branch of the checkout never reaches an external payment page, including via WebView or deep link
- [ ] Restore Purchases present and functional
- [ ] Paywall shows price, period, renewal terms, Terms of Use and Privacy Policy links
- [ ] Subscription entitlement verified server-side across devices
- [ ] Credits and in-app currency don't expire
- [ ] Loot box / randomized item odds disclosed before purchase
- [ ] No external-link steering without the matching entitlement
- [ ] No on-device mining; crypto features appropriately licensed
