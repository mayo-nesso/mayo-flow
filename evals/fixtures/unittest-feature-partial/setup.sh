# Builds a feature branch whose spec has tickets, one still open:
# spec and tickets first, then the code and its test. Run by evals.run.prepare_fixture.
set -e
git checkout -q -b feature/subtract
D=docs/10_features/2026_11_19_subtract
mkdir -p "$D"
cat > "$D/spec.md" <<'SPEC'
# Subtract

## Goal

`calc` gets a `sub(a, b)` function next to `add`.

## Implementation plan

1. Add `sub(a, b)` to `calc.py`, returning `a - b`.
2. Add a unit test for it.
3. Publish a release of `calc` to the internal package index (needs
   credentials the platform team has not issued yet).

## Test cases

- `sub(5, 3)` is `2`.
SPEC
mkdir -p "$D/tickets"
cat > "$D/tickets/01_add_sub.md" <<'T1'
# 1. Add sub

**Status:** done
**Blocked by:** none
**Touches:** calc.py, tests/test_calc.py

## Behavior

`calc.sub(a, b)` returns `a - b`.

## Acceptance criteria

- `sub(5, 3)` is `2`.

## Tests

- `SubTest.test_sub`.
T1
cat > "$D/tickets/02_publish_release.md" <<'T2'
# 2. Publish release

**Status:** blocked
**Blocked by:** 1
**Touches:** release process

## Behavior

A release of `calc` with `sub` is published to the internal package index.

## Acceptance criteria

- The new version is installable from the internal package index.

## Tests

- None (release step).

## Notes

Waiting on the platform team to issue publishing credentials; nothing in
this repository can unblock it.
T2
git add -A
git commit -q -m "docs: add spec for subtract"
cat >> calc.py <<'CODE'


def sub(a, b):
    return a - b
CODE
python3 - <<'PY'
p = "tests/test_calc.py"
s = open(p).read()
s = s.replace("from calc import add", "from calc import add, sub")
s = s.replace('\n\nif __name__', '''

class SubTest(unittest.TestCase):
    def test_sub(self):
        self.assertEqual(sub(5, 3), 2)


if __name__''')
open(p, "w").write(s)
PY
git add -A
git commit -q -m "feat: add sub to calc"
