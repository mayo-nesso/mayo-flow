# Legal and platform exposure (audit dimension 8)

Moved out of `SKILL.md`; read in full before auditing this dimension.

8. **Legal and platform exposure** — a small app with no revenue can still owe
   per-event penalties: the unit is per visitor, per session, per email, per
   image. Check each of the seven items below against the code and the config
   and record each as `applies`, `does not apply` or `not verified`, with
   evidence (file:line, the command run, the dependency list). `Does not
   apply` needs proof (a grep, the lockfile), not a feeling.
   a. **Age and children.** Any signup, profile or data collection that can
      involve minors: under-13 in the US (COPPA), minors under GDPR or the
      local data law. Is there an age gate or an adult confirmation before
      data is stored? Who supplies the child's data, the child or an adult?
      Does the store listing target children? Is there third-party analytics
      or advertising?
   b. **Third-party resources loaded at runtime.** Fonts (Google Fonts), CDN
      scripts, icons, maps, embedded video, tracking pixels: each one sends
      the visitor's IP to someone else (a Munich court awarded one visitor
      EUR 100 over Google Fonts, 2022). Prefer bundled or self-hosted. Grep
      for the font hosts, `@import`, `<link>`, absolute URLs in assets and for
      packages that fetch fonts or assets at runtime (for example
      `google_fonts`).
   c. **Session recording and input capture.** Session replay, screen
      recording, heatmaps, keystroke capture. In some US states this can be
      treated as wiretapping (California CIPA). Check the SDK configuration:
      replay off, or on only with consent and masked inputs.
   d. **Outgoing email.** A marketing or "we launched" message needs an
      unsubscribe link and a postal address in every message (US CAN-SPAM).
      Transactional email is different. `Does not apply` if no email is sent
      or collected.
   e. **Subscription checkout.** Price, billing period, automatic renewal and
      how to cancel are visible next to the subscribe button, not only on a
      linked page (store rules; California automatic-renewal law). Check the
      restore and refund paths too.
   f. **User uploads and published content.** If users upload or publish
      content that others can see, a registered DMCA agent (a small US fee)
      is needed for safe harbour, plus a takedown process. `Does not apply`
      if nothing uploaded is shown to anyone else.
   g. **Store policy drift.** For an Android app, check the restricted permissions
      and declarations against the latest Google Play policy update (location
      scope, local network, contacts, call log/SMS, all-files, accessibility) and
      the account items (trader status, Japan payments authorization). Use the
      checklist in `mayo-flow-store-preflight` section 3, item 7 rather than duplicating it.
      For an iOS app, check the account-termination triggers listed there (hidden
      or obfuscated features, remote flags, UGC/AI safeguards, bait-and-switch
      subscriptions, near-duplicate apps, linked accounts).
   Also check that what the app tells people (privacy summary, consent text,
   store privacy forms) matches what it really sends: compare it with the SDKs
   in the dependency list and the network calls.
   **Limits of this dimension.** The penalty figures commonly quoted for these
   items (for example about US$53K per child, per email or per violation,
   about US$5K per session, about US$150K per work) come from a social-media
   checklist and are **not verified**. Do not quote them in a report without a
   current source, and label them as order of magnitude. Jurisdiction matters:
   US federal and state laws bind the app's US users, so check where the app
   is actually distributed and who uses it. This is a way to find exposure, not
   legal advice: findings go to the user and, before public launch, to a lawyer.
