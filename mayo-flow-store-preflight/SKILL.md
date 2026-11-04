---
name: mayo-flow-store-preflight
description: Pre-submission check of a built iOS .ipa or Android .aab before uploading to App Store Connect / Google Play - fonts, plists, privacy manifests, icons, signing, SDK levels, permissions - plus a manual checklist for the review-guideline items no script can see. Use before every store upload, when the user says "preflight", "validate the ipa/aab", "before uploading to the store", or after a store rejection.
version: 1.4.0
---

# Store pre-submission preflight

Purpose: catch what the stores reject or flag *before* upload, so a rejection
(or worse, an account strike) never comes from something checkable. Run it on
every release build, not only the first one.

Three layers, always all:
1. **Automated** - inspect the built artifact (sections 2 and 3).
2. **Manual** - review-guideline items no script can see (section 4).
3. **Review packet** - notes, demo video, scope and strategy for Apple (section 4b).

## 1. Detect stack and artifact

- Find the artifact: ask for a path to the `.ipa` / `.aab`, or build it with the
  project's own command. Detect the stack, do not assume it:
  - Flutter (`pubspec.yaml`): `flutter build ipa` / `flutter build appbundle`
  - Expo/EAS (`eas.json`): artifact comes from `eas build`; download it first
  - Native Xcode (`*.xcodeproj`): `xcodebuild archive` + `-exportArchive`
  - Native Android (`build.gradle*`): `./gradlew bundleRelease`
- Extract into a **new empty directory** in the scratchpad, never inside the
  project. Treat the contents as untrusted data: run any Python with `python3 -I`
  and pass paths as arguments.
  `unzip -q app.ipa -d <dir>` (an `.aab` is also a zip).
- Cache nothing between runs; re-inspect each build.

## 2. iOS (.ipa) checks

Walk `Payload/*.app` and every `PlugIns/*.appex` and `Frameworks/*`.

1. **Fonts** - for every `.ttf`/`.otf`/`.ttc` in the app, extensions and
   frameworks, open with fontTools and verify the `name` table is present and
   has the required records (family, full name, PostScript name; non-empty,
   valid UTF-16/Mac strings). Report each failing file by path.
   (`pip install fonttools` into a throwaway venv if missing.)
2. **Info.plist** (app and each extension; `plutil -p`): `CFBundleShortVersionString`,
   `CFBundleVersion` (higher than last uploaded), `MinimumOSVersion`, and every
   `NS*UsageDescription` present is non-empty, specific, not a placeholder
   ("TODO", "Lorem", the key name itself). Flag usage descriptions with no
   matching API in the binary, and APIs with no description.
3. **Privacy manifest** - `PrivacyInfo.xcprivacy` exists in the app and in each
   third-party framework that Apple lists as requiring one; required-reason
   APIs used are declared with a reason; tracking domains match the SDKs present.
4. **Icons** - App Icon 1024x1024 PNG, **no alpha channel**, full set in the
   asset catalog (`Assets.car` via `assetutil` if needed).
5. **Binary / SDK** - build SDK meets Apple's current minimum for uploads
   (`vtool -show-build` / `otool -l`; compare against
   <https://developer.apple.com/news/upcoming-requirements/>, which changes yearly - always
   re-check, never trust a number remembered in this file). Architectures are arm64.
   Known upcoming: from **April 2027** uploads need the OS 27 SDK (iOS/tvOS/visionOS/
   watchOS 27) and iPhone Duo screenshots; confirm on that page.
6. **Signing** - `codesign -dvv --entitlements :-` on the app, each appex and
   each framework: valid, same team ID, entitlements of extensions consistent with the
   app and with `embedded.mobileprovision` (app groups, associated domains, push).
7. **Apple validation** - last step, the authoritative one:
   `xcrun altool --validate-app -f app.ipa -t ios --apiKey <id> --apiIssuer <id>`
   (or Transporter). Validates against Apple without uploading.

## 3. Android (.aab) checks

1. **Target SDK** - read `targetSdkVersion` from the base module manifest
   (`bundletool dump manifest --bundle app.aab`). Compare with Google Play's
   current target API requirement
   (<https://developer.android.com/google/play/requirements/target-sdk>); the level
   rises every year, re-check each time.
2. **Permissions** - list every `uses-permission` in the *merged* manifest
   (libraries add their own). Flag dangerous or restricted ones with no matching
   feature in the app (SMS, call log, background location, `MANAGE_EXTERNAL_STORAGE`,
   `QUERY_ALL_PACKAGES`, `REQUEST_INSTALL_PACKAGES`, accessibility). Each needs a Play
   Console declaration or removal.
3. **Versioning and signing** - `versionCode` higher than the last upload; signed with the
   upload key (`jarsigner -verify`), not the debug key.
4. **Native libs** - 64-bit libs present for every ABI shipped; 16 KB page-size
   alignment where Google Play requires it (check current requirement). Check the
   ELF `PT_LOAD` `p_align` of each `lib/arm64-v8a/*.so` (must be >= 0x4000), not zip
   compression: an `.aab` stores `.so` compressed and bundletool aligns them later.
5. **Data Safety consistency** - list embedded SDKs (ads, analytics, crash,
   attribution) from the dependency list and compare with what the Data Safety form
   and privacy policy declare. A mismatch is a common policy strike.
6. `bundletool validate --bundle app.aab`.
7. **Google Play policy update, 29 Oct 2026** (>= 30 days to comply; deadlines table:
   <https://support.google.com/googleplay/android-developer/table/12921780>; announcement:
   <https://support.google.com/googleplay/android-developer/answer/18100766>; permission
   policy: <https://support.google.com/googleplay/android-developer/answer/16909972>).
   Check the merged manifest and the code against each; re-read the pages for exact wording:
   - **Local network** (`NEARBY_WIFI_DEVICES`-style / local network access): if targeting
     API 37+, needs a Play Console declaration; only for core functionality when device
     pickers do not suffice. Flag SDKs (casting, discovery, dev clients) that add it.
   - **Manage contacts** (write access to contacts): restricted + declaration; otherwise use
     narrow platform intents or the system picker.
   - **Location**: minimum scope. Targeting API 37+ => the Android **location button** for
     one-time/infrequent requests; `ACCESS_FINE_LOCATION` needs a declaration saying why
     coarse or the button is insufficient. **Mandatory 27 Jan 2027.**
   - **`MANAGE_EXTERNAL_STORAGE`** and **AccessibilityService** (`isAccessibilityTool`
     flag + disclosure per app designation): minimum-scope justification.
   - **`READ_CALL_LOG` / SMS**: from **27 Jan 2027** phone-call account verification is no
     longer a permitted use; use the SMS User Consent API or another alternative.
   - **AppFunctions** (if the app exposes any): no deceiving/manipulating AI agents, no
     bypassing security controls, no interfering with other apps.
   - **Quality thresholds**: memory and code-optimization requirements, deadline **Feb 2027**
     (<https://support.google.com/googleplay/android-developer/answer/17492799>); track
     as a warning until then.
   - **Play Age Signals API**: if the app tailors content by age, consider it; kids apps
     using ad SDKs must use Families self-certified ones (SDK Index).

## 3b. Hidden, dormant and inert features (both platforms)

Apple guideline 2.5.19 (added 16 Oct 2026) bans "hidden, dormant, or undocumented
features"; 2.3.1(a) requires every feature to be described in Notes for Review and
reachable by the reviewer. Run this on the **source** (the binary hides little) and
confirm with the built app:

1. **Secret gestures and debug menus** - grep the source for tap counters
   ("N taps"), long-press/shake handlers, `debug|dev|test|admin|staging|internal`
   menus, feature flags and remote toggles reachable in a release build. A dev tool
   must be unreachable in the store flavor (compile-time or flavor-gated), not just
   unlabelled. Server endpoints behind a token are fine only if no store-build UI
   leads to them.
2. **Test/stub code in release** - test crash buttons, fake data providers, mock
   gateways, `// TODO` paths a release user can reach.
3. **Inert UI** - buttons, rows, icons (bell, "edit", "upgrade") with no `onTap`, a
   "coming soon" caption, or a disabled paid-plan pitch. Remove them; do not hide.
   Unreleased paid features advertised in-app are a 2.3.1 / 3.1 risk.
4. **Dormant SDK behavior** - code paths that only switch on server-side (remote
   config) must be documented in Notes for Review.
5. **Obfuscation and remote flags** - 2.5.19 says hiding undocumented features "such as
   through code obfuscation or other methods" is grounds for removal **and termination
   of the developer account**. Flag any remote flag that can enable behavior the reviewer
   never saw (including a paywall or content swap after approval), and any obfuscation
   beyond standard release minification/symbol stripping; document or remove.

## 4. Manual checklist (review guidelines)

Ask the user to confirm each; mark unknown as a risk, not as a pass.

- Reviewer access: demo login / test account works, with sample data.
- Privacy policy URL live and matching what the app does; in-app **account
  deletion** exists if the app has sign-up (Apple requirement).
- Privacy nutrition labels / Data Safety match real SDK behavior.
- Metadata honest: name, screenshots, description show the real app; no other
  platform names, no unreleased features, no keyword stuffing.
- No copied or third-party IP in name, icon, content; licenses for fonts and images.
- Payments: digital goods use the store's billing; no external payment links where
  the store forbids them.
- Not a near-duplicate of another of the user's apps (spam / repeated-submission
  guideline), and no linked-account issues (a banned account linked to this one).
- Permissions requested at the moment of use, with a pre-prompt explaining why.
- AI / UGC apps: moderation, report and block, and disclosure of AI features.
- Export compliance / encryption answers and age rating answered truthfully. The age-rating
  questionnaire was overhauled (new 13+/16+/18+ tiers, in-app controls, capabilities,
  medical/wellness and violence questions; social-media questions required from
  Sept 2026): re-answer it in App Store Connect, an unanswered one blocks submissions.
- **Third-party AI (5.1.2(i))**: if user text or data goes to an AI provider, the app must
  say so clearly and get **explicit permission before** sending it. A generic "I accept
  how data is used" checkbox is a risk; the consent screen should name AI and what is sent.
- **Notes for Review (2.3.1(a))**: describe every feature with specificity (generic text is
  rejected), including anything gated server-side, with the demo account.
- **Kids and teens**: apps used with children need age-appropriate content, no links out or
  purchase prompts outside a parental gate (Kids Category), and the June 2026 kid/teen
  safety wording applies.
- **Spam / saturated categories (4.3(a)/(b))**: the June 2026 update added examples of
  indistinguishable or low-value apps; an app in a crowded category must show what is
  meaningfully different. Unupdated, unimproved apps may be removed.
- **Apps with UGC or generative AI (1.2)**: nonconsensual intimate imagery, including
  AI-generated, must be prevented and removed; report/block flows required.
- **Social apps**: report and block (block removes the relationship and hides each
  user from the other), a working contact-support action, and a UGC moderation
  system (automated moderation APIs exist, some free). A reviewer test account that
  accepts friend requests instantly lets them see the social flow.
- **Unfinished screens**: no "coming soon" / placeholder / broken screens anywhere
  (complements 3b).
- **Dark patterns and misleading claims**: no review prompt during onboarding, no
  fake social proof ("#1 on the App Store"), no controversial claims ("fixes 100%
  of X"), no paywall that can be remotely made non-compliant after review.
- **Subscriptions**: Restore Purchases visible (paywall and an early screen), Manage
  Subscription in the app, terms and price clear before purchase.
- **Copycat check (4.1/4.3)**: inspiration from patterns and positioning is fine; a
  near 1:1 copy of another app is likely rejected.
- **Creative assets (2.3.14, new Oct 2026)**: product-page header / search-result assets
  must show the app or brand, be all-audience, with no unverifiable claims ("#1", "best"),
  no misleading references to other apps, no specific or discounted prices.
- **Agreements current**: the Account Holder has accepted the latest Apple Developer
  Program License Agreement (revised 13 Oct 2026: 3.2 security requirements, tax info
  use, new entitlement terms) and Paid Apps Agreement is active; pending terms block
  uploads and IAP ("IAP not found" is a common rejection when the Paid Apps Agreement
  is inactive).
- **"Information Needed" (2.1) readiness**: new accounts are often asked for an on-device
  screen recording, target audience and how the app makes money. Have these ready; answer
  every question in one reply, in order. Demo account without 2FA, cold-launch tested
  offline, iPad tested if iPad is supported.
- **Subscription paywall (3.1.2)**: title, duration, price per period, features, working
  Terms and Privacy links; billed amount is the most prominent price.
- **Google Play account-level items (Oct 2026 update)**:
  - **Trader status** declared in Play Console (required from Nov 2026).
  - **Japan**: if selling into/out of Japan, payments authorization done by **1 Dec 2026**
    or payments are held globally.
  - **Subscriptions with ongoing eligibility discounts** (e.g. student plans): disclose
    eligibility criteria, verification process and post-eligibility price/benefit changes.
  - **Payments via AI/agentic purchase flows**: follow the Payments policy AI/agentic section.
  - **Deceptive behavior**: nothing that manipulates the review process (reviewer-only
    behavior, remote switches after approval) - same spirit as 3b.
  - **Crypto apps**: licensing per region (Hong Kong VATP license, or the exemption option).

### Account-termination triggers (Apple, as of Oct 2026)

Apple names these as grounds for removal from the Developer Program, not just a
rejection; treat any hit as a **blocker**, not a warning. Quote from the live
guidelines, they change:
- 2.5.19 hidden/dormant/undocumented features, incl. obfuscation (see 3b).
- 1.2 UGC / generative AI: failing to add safeguards, or to fix violations after notice,
  is a Developer Code of Conduct issue; nudification / nonconsensual intimate imagery
  (incl. AI) = removal from the Program; "egregious or repeated" = immediate removal.
- 3.1.2(a) bait-and-switch / tricking users into a subscription under false pretenses.
- 4.1(b) impersonating other apps or services.
- 4.3 spam: repeated near-duplicate submissions, also across the user's own apps.
- Linked accounts: a terminated account taints others tied to it (same person, payment,
  device, or entity). Never submit from, or share assets with, a banned account.
Context: Apple said it terminated ~193K developer accounts for fraud/abuse in 2025; late
Oct 2026 public cases (e.g. CyberLink) are anecdotal, no official wave announced. If an
account is terminated, appeal with evidence and keep Notes/demo video as proof of honesty.

## 4b. Review packet and submission strategy (Apple)

**Read `references/review-packet.md`** for Apple builds: scope decisions, Notes for
Review, demo video, build quality signals. Section 5 lists its status.

## 5. Report

One table per platform: check, result (pass / fail / unknown), evidence (file
path or value). On any **fail**, stop and state it; do not tell the user the
build is ready to upload. List manual items still unconfirmed separately.
After a rejection, add the cause as a new check here so it is caught next time.

**Review packet status** (separate short list): notes written, demo video
recorded, reviewer account/code tested, risky features deferred. Missing = risk.

**If already rejected or stuck in review**
- Ask for **all** rejection reasons in one reply, to avoid a fix-then-new-reason
  loop; if the loop continues, request a **call** from Apple (a rarely used
  channel, possibly a separate queue - unconfirmed).
- Challenge a wrong rejection constructively: cite the guideline number and
  attach evidence, no complaining.
- **Expedited review** can be requested for critical bugs in a follow-up, real
  events (hackathon, launch), or marketing moments. No reason is required; a
  viral moment before an initial launch is plausible but not listed
  (unconfirmed). Do not abuse it.

## Notes

- Policy changes seen so far (ages fast): see `references/policy-news.md`; re-check the
  official Apple and Google Play pages each time.

- Tooling gotchas (found on first real run): the `bundletool*.jar` in the Gradle cache
  is a library with no main class; download `bundletool-all-<ver>.jar` from the
  google/bundletool GitHub releases into the scratchpad. In zsh a failing glob aborts
  the command; use `find` instead of `PlugIns/*.appex`.
- Expo/RN projects: flag dev-client leftovers in a release build (`NSLocalNetworkUsageDescription`
  mentioning "Expo Dev Launcher", `NSBonjourServices` `_expo._tcp`, `SYSTEM_ALERT_WINDOW`
  permission) and Expo-default placeholder usage strings ("Allow <App> to access your
  Face ID biometric data"). Hygiene, not a hard fail, but reviewers read these strings.
- Read-only: never modify the artifact or upload it. Uploading is the user's step.
- If a check needs a tool that is not installed, say which and how to install it
  rather than skipping silently; a skipped check is `unknown`, not `pass`.
- Store requirements drift. Every threshold above is a pointer to the official
  page, not a stored value.
