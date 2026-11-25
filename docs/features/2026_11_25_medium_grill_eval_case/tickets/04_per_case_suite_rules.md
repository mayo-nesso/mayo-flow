# 04. Prefactor: per-case leak words and fixture-import rule

**Status:** todo
**Blocked by:** none
**Touches:** tests/test_evals_suites.py (`FeatureStartE2eSuiteTest`)

## Behavior

Prefactor so the `waitlist` case is an easy change. The e2e suite test holds
its leak words and the forbidden fixture import per case instead of one
global list and a hard-coded `listcli`: shared leak words plus a per-case
list, and each case's hidden dir is checked only against its own fixture
package (spec decision 12 b, c). No case changes; the two existing cases
check exactly what they check today.

## Acceptance criteria

- A per-case table gives, for each case id, its extra leak words and its
  fixture package (`listcli` for both existing cases).
- `test_feature_text_does_not_leak` checks shared plus per-case words.
- The import test (renamed off `listcli`) checks `hidden/<case>/*.py` against
  that case's package only, and fails when a case has no entry in the table.
- Existing test outcomes unchanged; full suite green.

## Tests

- Refactor of test code only: the existing tests are the safety net and must
  stay green before and after. The one new behavior, "a case missing from the
  per-case table fails", is shown red by temporarily dropping an entry, and
  that output is shown.
- Red must be observed for that new assertion before it is relied on.
