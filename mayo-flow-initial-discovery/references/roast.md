# Roast: stress the assumptions

The catalogue finds questions nobody asked. The roast attacks the answers
everyone already believes. It looks for the blind spot that is inside the
plan itself: an assumption that, if false, makes the plan not worth building.

Tone: blunt, specific and fair. Attack the plan, never the person. Every
attack ends with something the user can do (a question, a cheap test or a
kill criterion). No vague doubt ("this might not work"). If you have no
evidence and no reasoning, you have no attack.

Run it twice in a discovery pass: once on the plan before the rounds, and
again on the decisions the rounds produced, because a fresh decision is the
least tested one.

## 0. Cover every aspect first, then go deep

The roast is **general before it is deep**. Do one sweep across every aspect
of the app below and ask at least one general question in each. Only then
go deep on the few assumptions that score highest. Do not spend the whole
roast on the technical side because it is the easiest to attack: product,
people, money, law and operations fail projects just as often.

Keep the sweep questions general and plain. They should make sense for any
app. Specific details come later, in the deep attacks.

| Aspect | General questions to ask |
|---|---|
| **Problem and value** | What problem is this, exactly? How painful is it, and how often? What do people do about it today? What would make them say "I can't go back"? |
| **Users** | Who is the first user, by name and situation? Who is the buyer, if different? Who is affected but never asked? Which user do we not want? |
| **Competition and alternatives** | What is the free or default alternative? What does the best competitor do that we do not? Why would someone switch, and what does switching cost them? |
| **First use and habit** | What happens in the first 5 minutes? Why come back on day 2, day 10, day 60? What if they never do? |
| **Core experience** | What is the one thing that must feel great? What is the worst moment in the flow? What does a bad result look like, and who sees it? |
| **Trust and quality** | What if the product is wrong, and the user believes it? Who checks? What is the most embarrassing failure we could have in public? |
| **Data and content** | Where does it come from? Who owns it? What goes stale? What happens to it when a user leaves? |
| **Technology** | What is the riskiest technical bet? What if the vendor changes price, terms or API? What is hard to change later? Where is the single point of failure? |
| **Money** | Who pays, for what, how much, and why? What does one user cost us? What if usage is ten times the estimate? What if nobody pays? |
| **Growth and distribution** | How does the first user hear about it? How does the 100th? What is the cost of getting a user? Does one user bring another? |
| **Legal, privacy and safety** | What personal data do we hold that we would not want leaked? Which rule could stop us? Who could be harmed, and how? |
| **Platform and channel** | What can the store or platform do to us? Which of its rules do we rely on staying as they are? |
| **Operations and support** | Who answers when something breaks at night? How do we know it is broken? How do users reach us? |
| **Team, time and money to build** | What is the true cost in weeks? What is cut first when late? Is one person a single point of failure? |
| **Measurement** | How will we know it works? Which number, from how many users, by when? What result would make us stop? |
| **Ethics and side effects** | Who could this hurt or annoy? What would a critic write about it? What are we optimizing that users might not want? |
| **Change over time** | What if the world, the law, the model or the standard we build on changes in a year? What if it succeeds and doubles? |

For each aspect write one line: **the sharpest general question**, our
current answer (or "none"), and a rating for confidence (high, medium, low,
none). Aspects with "none" or "low" go to the top of the deep round.

## 1. Build the assumption register

List what the plan takes for granted. Look in four places:

- **Stated:** "parents will study with their kids", "an LLM can write good
  questions for 6-year-olds".
- **Implied by the design:** a reminder is not needed because the schedule
  exists; a user will type a topic rather than ask a general chatbot.
- **About people:** who the user is, what they will do, how often, why they pay.
- **About the world:** a vendor's price, a law's date, a standard staying put,
  a platform allowing it.

Write each as a sentence that can be false: "Parents come back on their own
after the first session."

## 2. Rank them

For each one, rate **impact if false** (1–5) and **how little evidence we
have** (1–5). Attack in order of impact × doubt. Anything with impact 5 and
no evidence is a blocker for the roast, not a footnote.

## 3. Attack with these lenses

Use the ones that fit; do not run all of them on every assumption.

| Lens | The question |
|---|---|
| **Pre-mortem** | It is 12 months from now and this failed. Write the three most likely causes. |
| **Alternative** | What does the user already do today to solve this, for free? Why would they switch? |
| **Steelman the opposite** | Give the best argument for not building this, or for the opposite decision. |
| **Falsify** | What single observation would prove this assumption wrong? Can we get it cheaply? |
| **Numbers** | Put figures on it: cost per use, users needed, hours of work, review time. Does it survive a bad month? |
| **Dependency** | Which vendor, person or rule can remove the floor from under this? |
| **Scale and time** | What breaks at 10x users, or after a year of data? What ages badly? |
| **The uncomfortable user** | The user who is tired, in a hurry, hostile, or not the person you designed for. |
| **Reversibility** | If wrong, how expensive is it to undo? Do the irreversible ones first. |
| **Scope** | What is in the MVP that nobody would miss? What is missing that everyone would? |

## 4. Verdict per assumption

- **Holds:** evidence supports it. Say which.
- **Cheap test:** name the smallest experiment, its cost and the result that
  would change the plan. Put it in the plan as a work item or a beta question.
- **Kill criterion:** "If X is below Y after Z, we stop or change course."
  Write the number and the date.
- **Decision needed:** becomes a catalogue question, with options and a
  recommendation.
- **Accepted risk:** the user knowingly keeps it. Record their reasoning in
  their words. Do not argue it twice.

## 5. Output

`docs/05_discovery/YYYY_MM_DD_roast.md`, in this order:

1. **The three biggest threats**, in two sentences each.
2. **Coverage sweep**: one row per aspect from section 0 (sharpest general
   question, current answer, confidence).
3. **Assumption register**, a table: assumption, impact, doubt, lens used,
   verdict.
4. **Attacks that need a decision**, with links to the new catalogue entries.
5. **Cheap tests and kill criteria**, each with an owner phase and a date.
6. **Accepted risks**, with the user's reasoning.

Feed the results back: new questions go into the catalogue with the next id,
tests and kill criteria into `PLAN.md` (a risks or decisions row) and the phase
docs, and accepted risks into the answer line of the entry they came from.

## Running it with the user

Start with the coverage sweep: show the user the aspect table with your one
general question per aspect and ask them to answer or skip each, in rounds of
4 aspects. Then roast the deep attacks in short rounds of at most 4 at a time,
most dangerous first. For each, state the attack in two or three sentences, then use
`AskUserQuestion` with options such as: change the plan, run the cheap test,
set a kill criterion, accept the risk. If the user pushes back with a good
reason, say so and drop the attack. If they push back without one, keep it
open once, and then move on.

## Example deep attacks (from a real pass on a parent-and-child study app)

These are examples of the shape, not a checklist. The sweep in section 0
stays general; these show how a general question becomes a specific attack.

- **Alternative.** "A parent can ask a general chatbot the same thing for
  free. Why open this app?" The plan had answers (curriculum anchoring, three
  short questions, hints, spaced review) but no way to check that parents
  value them. Cheap test: give ten families both tools for two weeks and ask
  which they opened.
- **Falsify.** "A second model checking the answer catches wrong answers."
  Two models can agree on the same wrong answer. Cheap test: plant fifty known
  wrong questions and measure how many the check rejects.
- **Numbers.** "Costs are fine because of the cache." Unanchored sessions are
  not cached and now pay for a second model call every time. Put a number on
  the share of such sessions in the beta before setting the price.
- **Pre-mortem.** "Nobody returns for the second review." The schedule says
  "back in 3 days" and nothing reminds the parent. Kill criterion: fewer than
  a third of first-session families start a second session within 10 days.
- **Scope.** "The MVP includes a reviewed bank, a checker, tiered quotas and
  staged search in one phase." Is that one phase or three? Cut list before
  the spec.
