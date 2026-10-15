# Scenario checklist

Use it to find whole areas the catalogue is missing. Skip what does not
apply and say so in the catalogue. Each line is a prompt for a question, not
a question itself: turn a prompt into an entry only when the docs do not
already answer it.

## 1. The lifecycle of every entity

For each thing the system stores (user, child, project, order, item, session):
- **Create:** who can, how many, what if it is a duplicate, what if it is invalid.
- **Read:** who can see it, including the owner's other devices.
- **Share:** can two people own or see it? (two parents, a team, a family)
- **Change:** which fields, by whom, and what depends on the old value
  (a grade, a plan, a price, a name).
- **Delete:** what cascades, what is left behind (orphans, shared caches,
  logs, backups), and can it be undone?
- **Restore or migrate:** new phone, reinstall, merged accounts.
- **Expire or age:** what changes with time (a school year, a trial, a
  retention period, a certificate).

## 2. Identity and accounts

- Anonymous, then registered: when is the account asked for, and what if it
  already exists for that person?
- Several devices, one person. One device, several people.
- Sign-in providers: what if one is removed, or the email is private or changes?
- Adults and minors: who is the user, who is the subject of the data, who consents?
- Account recovery and support: what does a person do when locked out?

## 3. Money

- What is free, what is paid, and what exactly does paid add? (Numbers are proposals.)
- Trial, price by country, promo codes, testers and beta users.
- Cancel, expire, refund, billing problem, grace period, restore, upgrade or
  downgrade, family sharing. What happens to data and limits in each?
- Unit economics: cost per unit of work versus price. What is the daily cap
  and what happens when it is hit?
- The store's own rules on purchases and on what the app may say about them.

## 4. The core flow (the thing users came to do)

- The empty state, the first use, the most common use, the heaviest use.
- Input that is too long, too short, off-topic, in another language, pasted
  from somewhere else, or sensitive.
- Interrupted flow: user leaves halfway, app killed, phone call, no network.
- Partial success: three items expected, two delivered.
- Repeat: same request twice, two devices at once, a retry after a timeout.
- What counts as "done", and how is it measured?
- Undo, correction, "another one", "this is wrong".

## 5. Generated or third-party content (if any)

- Who checks that it is correct, not only that it is safe?
- What if it is wrong and shared with everyone (a cache)?
- Facts about specific people, books, places: high risk of invented details.
- Format limits: length, notation, images, tables, reading passages.
- Reporting, flagging, review queue, and who reviews.
- Changing the prompt or model: what happens to stored content and cost?

## 6. Retention and engagement

- What brings a person back? Reminders, streaks, email. What is promised on
  screen, and who keeps that promise?
- What harms them: too many reminders, pressure on children, dark patterns.

## 7. Reliability: each dependency fails

For every external service (model provider, payments, auth, storage, maps):
- Down, slow, rate-limited, changed API, changed price, changed terms.
- What does the user see, and what is served instead (cache, bank, message)?
- Time limits of the platform you run on (function timeouts, background work).
- Backups, restore, migrations to production, who is alerted.

## 8. Abuse and security

- Cheap account creation and quota evasion. Scraping. Prompt injection
  through every input channel (text, voice, files).
- Secrets in the client. Who can write to which table, and does anything check
  that two related rows agree?
- Rate limits by identity level. Alerts on cost.

## 9. Privacy and law

- Which personal data is stored, sent to which vendor, for how long, in which
  region?
- Sensitive data users type into free text (health, names, addresses).
- Consent: what, when, recorded how, and for whom?
- Minors. Transfers abroad. Retention and deletion. Export.
- Vendor terms: training on inputs, retention, sub-processors.
- Dates on which a law starts to apply, against the launch date.
- What needs an expert, and when? Say plainly what the assistant's review is
  not (it is not legal advice).

## 10. Platform and store

- Store categories (kids, family), age ratings, privacy labels and data forms.
- Required flows: account deletion, restore purchases, sign-in rules.
- Minimum OS versions, device types, orientation, dark mode, accessibility,
  permissions denied (microphone, notifications), offline behaviour.
- Language and register of the interface (formal or informal), locale, dates.

## 11. Operations for a small team

- Support channel. How feedback arrives during the beta. Who recruits testers.
- Analytics events, and what must never go into them.
- Spend alerts, error tracking, a place to look when something breaks.

## 12. The project itself

- What date matters (a law, a school year, a season)? Is the plan compatible?
- Which phase has grown too large? Which ones can run in parallel?
- What makes the MVP "done" beyond each phase's checks?
- What is deliberately out of scope, and is that said in the scope?

## 13. What changes over time

- The external standard the product is built on (a curriculum, an API, a
  regulation): what if it changes in a year?
- The product's own data: a new prompt version, a new schema, a new edition.
- Users: grade, plan, family size, country, language.

## Heuristics for questions nobody has asked

- "What happens when it is empty / offline / duplicated / deleted / late /
  done twice?"
- "Who else is involved that the model does not represent?"
- "What is stored that the user did not mean to give us?"
- "What does a competitor's user complain about?"
- "What must be true on launch day, and who checks it?"
- "Which decision here is cheap now and expensive after data exists?"
  (dimensions, keys, ownership, formats): raise these first.
