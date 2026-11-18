---
name: mayo-flow-store-preflight
description: Check a built iOS .ipa or Android .aab before uploading to App Store Connect / Google Play (fonts, plists, privacy manifests, icons, signing, permissions), plus a manual review-guideline checklist. Invoke manually before every store upload.
version: 1.4.3
disable-model-invocation: true
---

# Store pre-submission preflight

Purpose: catch what the stores reject or flag *before* upload. Run it on
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

Covers fonts, Info.plist, privacy manifest, icons, binary/SDK, signing and Apple
validation of the `.ipa`.

**Read `references/ios.md` when the artifact is an .ipa.**

## 3. Android (.aab) checks

Covers target SDK, permissions, versioning and signing, native libs, Data Safety
consistency, `bundletool validate` and the Google Play policy update of 29 Oct 2026.

**Read `references/android.md` when the artifact is an .aab.**

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

- Community reference: https://github.com/mjmirza/app-store-compliance (App Store
  compliance checklist/rules). Third-party, not official; use it to cross-check section 4,
  and verify anything it claims against Apple's own pages.

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
