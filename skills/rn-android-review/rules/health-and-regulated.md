# Health, Medical & Other Regulated Apps (Android)

Read this whenever the app touches health, fitness with medical framing, patient data, telehealth, clinical workflows, or insurance claims. Play applies stricter rules here, and those rules are **separate from and additional to** regulatory obligations like HIPAA — passing Play review says nothing about being compliant, and being compliant says nothing about passing Play review. Report them as two distinct tracks.

## Health Connect restricted data policy

Access to Health Connect requires a **declared, approved use case**. Google reviews the request; an app that reads health data without an approved declaration loses access.

Once granted, the data is restricted:

- No advertising or marketing use
- No sale, and no transfer to data brokers or information resellers
- No transfer for any purpose the user wasn't told about
- A privacy policy that **specifically** covers health data handling — a generic policy is a violation
- An **in-app disclosure and consent** step before the permission request, separate from the system runtime prompt

```ts
import { initialize, requestPermission } from 'react-native-health-connect';

// 🔴 permission request with no prior in-app rationale
await requestPermission([{ accessType: 'read', recordType: 'HeartRate' }]);

// ✅ show a disclosure screen naming the data types and the purpose first,
// get explicit consent, then request.
```

The disclosure screen is a policy requirement, not a UX nicety, and it's the part RN teams most often skip because the library doesn't force it.

## Health apps policy and health misinformation

- Claims must not contradict established medical consensus.
- The app must not present itself as diagnosing or treating without the regulatory basis to do so.
- Certain categories need declarations and, in some markets, licensing evidence: telehealth, prescriptions, substance-abuse treatment, clinical trials, and unapproved substances.
- Listing copy matters as much as the app. "Cures", "diagnoses", and implied endorsement by a health authority are all enforcement triggers.

## Data safety

Health and fitness is a declared data category. If the app handles PHI, the form must reflect collection, sharing, encryption in transit, and a deletion path — and it must match the SDK inventory, including whatever your crash reporter collects.

## Sensitive permissions in health apps

Common in this category and each needs justification: `ACCESS_BACKGROUND_LOCATION` (visit detection), `BODY_SENSORS`, `ACTIVITY_RECOGNITION`, `CAMERA` (document and wound capture), `READ_MEDIA_IMAGES` (insurance cards — use the photo picker instead), `POST_NOTIFICATIONS` (medication reminders).

## The HIPAA-adjacent layer (Play does not check this — you must)

Play review does not validate HIPAA. But the same codebase facts drive both, so audit them in the same pass:

- **PHI at rest** — EncryptedSharedPreferences, Android Keystore, or SQLCipher. Never `AsyncStorage`, never plain SQLite, never a JSON cache file.
- **PHI in transit** — TLS 1.2+, no `usesCleartextTraffic="true"`, a scoped network security config if an exception is genuinely needed, certificate pinning where the threat model calls for it.
- **PHI in logs and crash reports** — Sentry/Bugsnag/Crashlytics breadcrumbs routinely capture request bodies and navigation params containing patient identifiers. This is the most common real leak in RN healthcare apps, and it silently creates a Data safety disclosure you never filed.
- **PHI in analytics** — event properties carrying MRN, DOB, or names. Same disclosure problem.
- **Screenshots and Recents** — `FLAG_SECURE` on activities showing PHI, which also blocks screenshots and screen recording.
- **Backup** — `android:allowBackup="true"` can ship PHI to the user's cloud backup. Set it false or use a backup rules file that excludes PHI stores.
- **Session handling** — inactivity timeout, biometric re-auth, token revocation on logout.
- **BAAs** — every third-party processor that can see PHI needs one. An SDK that sees PHI with no BAA is a finding regardless of what Play says.
- **Deletion** — the account deletion Play requires (in-app *and* a public web URL) has to interoperate with your retention obligations. State the retention period in the flow rather than silently keeping records.

```xml
<!-- 🔴 -->
<application android:allowBackup="true" android:usesCleartextTraffic="true">

<!-- ✅ -->
<application android:allowBackup="false">
```

```ts
// 🔴 leaks PHI into a third-party processor
Sentry.setContext('patient', { mrn, dob, name });
analytics().logEvent('view_record', { patientId, diagnosis });

// ✅
Sentry.init({ beforeSend: scrubPHI, beforeBreadcrumb: scrubPHI });
analytics().logEvent('view_record', { recordType: 'lab' });
```

## Other regulated categories, briefly

- **Finance / lending** — personal loan apps need disclosures (APR, term, fees, a representative example). The specifics matter:
  - **Short-term loans (repayment in full within 60 days) are banned globally**, with one narrow Pakistan exception added in July 2025.
  - **US maximum APR is 36%.**
  - Per-country licensing evidence is required, and the list is long: India (RBI DLA list), Indonesia (OJK), Philippines (SEC + CoA), Nigeria (FCCPC), Kenya (CBK), Pakistan (SECP, one app per NBFC), Thailand (≥15% needs BoT/MoF).
  - The developer entity must hold or clearly disclose the licence — and under Apple 5.1.1(ix) regulated apps must ship from a **legal entity account, not an individual developer account**.
- **VPN** — must use the `VPNService` API as its core functionality, declare it in the Console, and must not collect data outside the disclosed purpose.
- **Accessibility API** — using it for anything other than genuine accessibility is a suspension risk, and it is a common shortcut in RN automation features.
- **Government / civic** — must be published by or on behalf of the government entity.

---

## Checklist

**Google**
- [ ] Health Connect use case declared and approved
- [ ] In-app disclosure and consent precede the permission request
- [ ] Health data not used for ads, not sold, not transferred to brokers
- [ ] Privacy policy specifically covers health data
- [ ] Health claims consistent with medical consensus; no unbacked diagnosis or treatment claims
- [ ] Category declarations (telehealth, prescriptions, trials) submitted where applicable
- [ ] Data safety reflects health data collection, sharing, encryption, and deletion
- [ ] Sensitive permissions justified, declared, and minimised

**Regulatory — audit even though Play doesn't**
- [ ] PHI encrypted at rest in EncryptedSharedPreferences / Keystore / SQLCipher
- [ ] No PHI in logs, crash breadcrumbs, or analytics properties
- [ ] TLS enforced; no cleartext exception
- [ ] `FLAG_SECURE` on PHI screens
- [ ] `allowBackup` disabled or scoped to exclude PHI
- [ ] Inactivity timeout and biometric re-auth
- [ ] BAA in place for every processor that can see PHI
- [ ] Deletion flow (in-app and web URL) reconciled with retention obligations
