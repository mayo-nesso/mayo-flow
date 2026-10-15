---
name: mayo-flow-store-preflight
description: Pre-submission check of a built iOS .ipa or Android .aab before uploading to App Store Connect / Google Play - fonts, plists, privacy manifests, icons, signing, SDK levels, permissions - plus a manual checklist for the review-guideline items no script can see. Use before every store upload, when the user says "preflight", "validate the ipa/aab", "before uploading to the store", or after a store rejection.
version: 1.0.0
---

# Store pre-submission preflight

Purpose: catch what the stores reject or flag *before* upload, so a rejection
(or worse, an account strike) never comes from something checkable. Run it on
every release build, not only the first one.

Two layers, always both:
1. **Automated** - inspect the built artifact (sections 2 and 3).
2. **Manual** - review-guideline items no script can see (section 4).

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
- Export compliance / encryption answers and age rating answered truthfully.

## 5. Report

One table per platform: check, result (pass / fail / unknown), evidence (file
path or value). On any **fail**, stop and state it; do not tell the user the
build is ready to upload. List manual items still unconfirmed separately.
After a rejection, add the cause as a new check here so it is caught next time.

## Notes

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
