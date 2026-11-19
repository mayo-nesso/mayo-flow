# Builds a finished feature branch on top of the initial commit on main:
# spec first, then the code and its test. Run by evals.run.prepare_fixture.
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

## Test cases

- `sub(5, 3)` is `2`.
SPEC
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
