# Google Play — Restricted Content, UGC, Families, Misrepresentation

Play enforcement differs from Apple's in consequence: violations here can suspend the app *after* publication and, repeated, terminate the developer account. Treat findings in this file as release-blocking even when the app would pass Apple review.

## Restricted content

Covers sexual content, hate speech, violence, bullying, dangerous products (weapons, explosives, drugs, tobacco, unapproved substances), marijuana, alcohol, gambling, illegal activities, and sensitive events.

**Health-relevant edge**: unapproved substances and unapproved pharmaceuticals policies catch supplement and telehealth apps. If the app lists or facilitates access to medication, confirm the regulatory allowance for each market it ships to.

## User-generated content

Apps with UGC must implement:
- a content policy / user agreement prohibiting objectionable content
- **in-app reporting** of objectionable content and users
- moderation proportional to the content type, including removal of content that violates policy
- blocking of abusive users
- for apps where UGC is the primary purpose, a documented moderation approach in the Play Console declaration

Play additionally requires attention to **CSAE (child sexual abuse and exploitation)** — apps with UGC and social features must have CSAE standards, published in-app reporting, and a CSAE point of contact. This is a Play-specific declaration Apple doesn't ask for and RN teams routinely miss.

```ts
// Evidence to find in an RN UGC app
reportContent(id, reason)     // ✅
blockUser(userId)             // ✅
// plus a Console declaration; grep the repo for a moderation policy doc
```

## Families policy

If the app targets children or has a mixed audience:
- complete the Families self-certification in Play Console
- use only Play-certified ads SDKs in child-directed traffic
- no collection of AAID/persistent identifiers from children
- no leading children out of the app without a gate
- comply with COPPA/GDPR-K; a privacy policy is required regardless of audience

```xml
<!-- 🔴 in a child-directed app -->
<uses-permission android:name="com.google.android.gms.permission.AD_ID"/>
```

## Impersonation and misrepresentation

App title, icon, developer name, and listing must not imply affiliation that doesn't exist. Health apps must not imply endorsement by a health authority. Deceptive claims about functionality ("cures", "diagnoses") violate both this and the health misinformation policy.

## Repetitive content / minimum functionality

Play's spam policy mirrors Apple 4.2/4.3: apps with no meaningful functionality, WebView-only wrappers, and families of near-duplicate apps from one developer. Agencies shipping per-client RN builds should publish from the client's own Play developer account.

## Deceptive behavior

- The app must do what the listing says
- No fake updates, fake system warnings, or misleading push notifications
- No unexpected redirects to ad content or app stores
- Disclosed behavior must match actual behavior — this is where the **Data safety form** ties in (see `play-privacy-data.md`)

---

## Checklist

- [ ] No restricted content categories present, or the app holds the required approvals per market
- [ ] UGC: user agreement, in-app report, in-app block, moderation with removal
- [ ] CSAE standards and reporting contact if the app has social/UGC features
- [ ] Families self-certification completed if child-directed or mixed audience
- [ ] No `AD_ID` permission or persistent identifiers in child-directed traffic
- [ ] Ads SDKs are Play-certified for families traffic
- [ ] Title/icon/developer name imply no false affiliation or endorsement
- [ ] No health claims implying diagnosis or cure without regulatory backing
- [ ] Substantive functionality beyond a WebView wrapper
- [ ] Per-client apps published from the client's own developer account
- [ ] Notifications and in-app messaging aren't deceptive or ad-redirecting
