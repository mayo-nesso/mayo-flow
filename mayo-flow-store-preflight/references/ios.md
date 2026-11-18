# iOS (.ipa) checks

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
   re-check). Architectures are arm64.
   Known upcoming: from **April 2027** uploads need the OS 27 SDK (iOS/tvOS/visionOS/
   watchOS 27) and iPhone Duo screenshots; confirm on that page.
6. **Signing** - `codesign -dvv --entitlements :-` on the app, each appex and
   each framework: valid, same team ID, entitlements of extensions consistent with the
   app and with `embedded.mobileprovision` (app groups, associated domains, push).
7. **Apple validation** - last step, the authoritative one:
   `xcrun altool --validate-app -f app.ipa -t ios --apiKey <id> --apiIssuer <id>`
   (or Transporter). Validates against Apple without uploading.
