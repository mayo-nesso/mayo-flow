# Review packet and submission strategy (Apple)

Moved out of `SKILL.md`; read in full when building or checking the review packet.

## Review packet and submission strategy (Apple)

Goal: make the review effortless and boring. Reviews are subjective by design
(lenient vs strict reviewer is luck); this section widens the odds. Source:
field experience of an indie dev (initial review ~48 h, follow-ups ~1 day), so
treat as heuristics, not Apple policy. Items marked (unconfirmed) are the
author's own belief.

**Scope - decide before building the packet**
- **First submission = MVP.** More features means a more complex review. Reviews
  have two tiers: straightforward (~48 h) and escalation to a senior specialist
  (the ~14 day wait). Avoid tier 2 unless the app is legitimately complex
  (banking, health/biometric data, marketplace). Ask: which feature in this
  build could be cut and added in a later submission? Flag each risky one.
- **Risky features go in a later review, not the first**: transaction-abandon
  offers (allowed, but reviewer-subjective; may triage the build to the slow
  pile), exit offers / cancel-flow questionnaires with a cheaper plan (the plain
  "Manage subscription" deep link to the App Store subscriptions page is safe).
  Later updates may push boundaries, but always clearly and honestly, explained
  in the notes with a demo.

**Notes for Review - written for a total beginner**
- Concise bullets, written by a human (AI text tends to be vague; it must be
  understandable). Re-read it as someone who has never seen the app.
- Cover: what the app is in one line; whether login is needed (or demo
  credentials / a reviewer code that works); how to test purchases (sandbox,
  where the paywall is, where Restore Purchases is); a numbered main flow; how
  to test social features with a dedicated reviewer account; how photos, camera
  and other permissions are requested; what data leaves the device and to whom
  (e.g. moderation provider); where account deletion, support, privacy, terms,
  report/block live; anything gated server-side.
- **Demo video**: screen recording walking the whole app with a text overlay per
  section. Very high ROI; initial submissions without notes + demo may be
  auto-rejected (unconfirmed).
- Be honest: never sneak a behavior past review (e.g. changing a remote paywall
  after approval is a dark pattern and a ban risk).

**Build quality signals**
- Looks finished and useful: low-effort "slop" gets more scrutiny.
- Responsive across iPhone/iPad sizes, Dynamic Type, safe areas, native
  keyboard/sheets/navigation. Native SwiftUI has the larger surface area for
  these; cross-platform stacks (Expo etc.) can pass but need explicit checks.
- Privacy policy and terms as live static HTML pages, linked in-app and in
  App Store Connect; both stay reachable even when a subscription expires.
- Permissions requested properly, at point of use, with accurate strings.
- Everything works end to end: payments, restore, every advertised feature.
