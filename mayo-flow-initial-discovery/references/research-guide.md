# Research guide

Goal: learn from flows other people already solved, and find facts that
change the plan. Output: `docs/05_discovery/YYYY_MM_DD_research.md`.

## What to look up

1. **Similar products.** Three to six. For each: what the flow is, what you
   can copy, what to avoid. Look at onboarding, pricing and trial, what
   happens on cancel, how accounts and children or teams are modelled, how
   they bring users back, how they handle a wrong answer or a bad result.
2. **Platform and store rules.** Apple App Store guidelines, Google Play
   policies: account deletion, restore purchases, kids or family categories,
   sign-in rules, data-safety forms, review risks for this kind of app.
3. **Law.** The laws of the target country or countries: entry-into-force
   dates, rules for minors, sensitive data, consent, transfers abroad,
   retention. Check the date against the official text.
4. **Vendor limits and terms.** Timeouts, rate limits, regions, data retention
   and training terms, pricing changes, webhook delivery guarantees, what the
   SDK does in the edge cases you rely on (linking, retries, ordering).
5. **External standards the project depends on.** A curriculum, a data
   format, an API version: which edition is in force, what is changing, and
   in what format it can be obtained.

## How to record

- Every claim has a link.
- Mark the source: **[P]** primary (vendor docs, the law, the platform,
  a ministry) or **[S]** secondary (blogs, forums, articles). Prefer [P].
- When sources disagree, say so and mark the fact "confirm on the primary
  source". Do not pick one silently.
- Say what you could not open or verify. End the file with **Not verified**.
- Open with the findings that change the plan (numbered R1, R2 …), with the
  effect on the plan for each.

## What to skip

Products that add nothing beyond the ones already covered. Say so in one line
instead of researching them anyway.

## Then

Every finding that needs a decision becomes a catalogue question. Every
finding that corrects an existing doc (a wrong name, a wrong date, an old
edition) is fixed in that doc, in the same branch.
