---
name: mayo-flow-initial-discovery
description: Initial discovery pass before building - review what exists, research similar products, platform rules, law and vendor limits with links, write a catalogue of open scenarios and questions (each with options and a recommendation), roast the plan across every aspect of the app to stress assumptions and find blind spots, settle everything with the user in short guided rounds, and write every answer into PLAN, phase docs and specs. Use after specs or PLAN.md exist and before the next phase of code, when a new area opens up, or when the user says loose ends, "what am I missing", "roast me", stress test, poke holes, devil's advocate, pre-mortem or "rethink everything".
version: 1.1.0
---

# Initial discovery: find the loose ends and stress the plan while it is cheap

Time spent here is cheaper than a migration, a rewrite or a store rejection
later. The goal is not a long list of questions. It is a set of **decisions
that each have a home** in the project's docs, a set of **assumptions that
were attacked** and either held or got a test, and a short list of what is
still open and who owns it.

Two halves that need each other:

- **Discovery** finds the questions nobody asked (gaps).
- **Roast** attacks the answers everybody believes (blind spots).

It was extracted from a real pass on the Tudy project (a Flutter and Supabase
app). That pass turned ~46 questions into 27 recorded decisions, and it found
things nobody had asked about: a law starting before the beta, a curriculum
edition in flux, a review gap in the schema.

Argument (optional): the area or phase to focus on. Default: the whole project.
Two shortcuts: "roast only" runs steps 1 and 5 to 7 on an existing plan;
"discovery only" skips the roast steps.

## When not to use it

- Nothing is written down yet: run `mayo-flow-project-init` first. Discovery
  needs a PLAN or specs to question.
- One small, well-understood feature: the feature spec's "Decisions" section
  is enough.

## Rules that made it work

1. **Read before asking.** Never ask what the docs or code already answer.
2. **Every question carries a scenario, options with trade-offs, and a
   recommendation.** The user chooses; they should never have to design the
   options themselves.
3. **Facts have links.** A claim from memory is marked as unverified. Weak
   sources (blogs, forums) are marked as such.
4. **Ask in short rounds, most blocking first.** At most 4 questions per
   round, recommendation first. Group low-stakes items into one multi-select
   "accept the ones you agree with".
5. **Unselected is not rejected.** If the user did not accept a recommendation,
   keep it open with a note and ask again with different options. Do not
   treat silence as a no.
6. **The user decides, you state the risk once.** If they choose something
   you think is risky, record their reasoning in their words, add the caution
   as a note, and move on. Do not argue twice, and do not present your own
   review as a substitute for an expert (for example legal advice).
7. **An answer is not done until it has a home.** A row in the PLAN decisions
   table, a change in the phase doc, or a feature spec (spec first, code
   later). Commit per round.
8. **Answers raise new questions.** Add them to the catalogue with the next id
   instead of deciding on the spot.
9. **The roast is broad first, then deep.** Ask general questions about every
   aspect of the app (product, users, money, law, operations, not only tech),
   then go deep where confidence is lowest. Attack the plan, never the
   person, and end every attack with something the user can do.
10. **Stop when the questions that block the next phases are answered.** The
    rest stay open, each with its owner phase.

## Steps

### 1. Read the source material
PLAN, phase docs, specs, `CLAUDE.md`, and the code and schema that exist.
Note the project's own words, its conventions and where docs and code
disagree. Do not edit read-only spec folders.

### 2. Review what is built
Run the full test suite (`mayo-flow-run-tests`). Compare each phase's "done
when" with reality. Read the schema and main flows looking for gaps: rules
nothing enforces, states with no place, data that outlives its owner, free
text that may hold sensitive data, quota or abuse loopholes. Write it as a
dated review in the audits folder (findings with file:line, severity and the
phase that must handle it). Findings that need a product decision become
catalogue questions.

### 3. Research
See `references/research-guide.md`. Similar products and their flows,
platform and store rules, laws, vendor limits and pricing, and the current
state of any external standard the project depends on. Write
`docs/05_discovery/YYYY_MM_DD_research.md`. Put the findings that change the
plan first, and end with a "Not verified" list.

### 4. Write the catalogue
`docs/05_discovery/YYYY_MM_DD_loose_ends.md`, plus a short
`docs/05_discovery/README.md` if the folder is new. Use
`references/question-format.md` for the entry shape and
`references/scenario-checklist.md` to make sure whole areas are not missing.
Group by **tier**: A blocks the next phase or the first slice, B blocks
later phases, C is post-MVP or operations. Numbers (prices, quotas, limits)
are proposals, not facts, and are written that way.

### 5. Roast the plan
Follow `references/roast.md`. First the **coverage sweep**: one general
question for each aspect of the app (problem and value, users, competition,
first use and habit, core experience, trust and quality, data, technology,
money, growth, legal and privacy, platform, operations, team and time,
measurement, ethics, change over time). Then build the assumption register,
rank it by impact and doubt, and attack the top ones with the lenses in the
reference (pre-mortem, alternative, steelman the opposite, falsify, numbers,
dependency, and so on). Write `docs/05_discovery/YYYY_MM_DD_roast.md`. Every
attack becomes one of: a catalogue question, a cheap test, a kill criterion
or an accepted risk.

### 6. Run the rounds
Use `AskUserQuestion`. Order: sweep answers and tier A questions first. Write
the user's exact reasoning into the answer, including corrections and
clarifications (they often reveal a sharper requirement than the question).
After each round:

1. mark the entries `answered (date)` with an **Answer** line that says where
   it was written;
2. add or update the PLAN decision rows, phase-doc items and feature specs;
3. add new questions the answers raised;
4. commit: `docs(discovery): record answers for <topic>`.

When an answer changes the design a lot (for example "reviewed question
bank instead of on-demand only"), write the feature spec first and commit it
alone, then propagate.

### 7. Roast the decisions
Run the roast again, short, on what the rounds decided. A fresh decision is
the least tested one. Look especially for decisions that quietly grew the
scope, that depend on an unverified fact, or that contradict an earlier one.
Kill criteria and cheap tests go into `PLAN.md` and the phase docs.

### 8. Close
Re-list the open questions with their `Blocks` field. Check that no PLAN open
item duplicates a catalogue entry (move it into the catalogue and link it).
Update `docs/structure.md` for the new folder. Finish the branch with
`mayo-flow-branch-finish`. Tell the user: what is decided, what is deferred,
what is still open, which decisions rest on unverified facts, the three
biggest threats from the roast, and if any phase grew too large to run as
one.

## Practical notes

- Work on a branch such as `chore/discovery-pass`. If a phase is in progress
  with uncommitted files, use a separate git worktree so that work is not
  touched.
- Before rewriting a doc from a script, read the whole file first. Opening a
  file for writing empties it before it is read.
- Keep repo docs in the project's documented language, whatever language the
  conversation is in.
