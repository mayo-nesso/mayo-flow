# Android (.aab) checks

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
