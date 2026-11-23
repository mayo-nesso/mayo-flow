# A larger feature, feature/calc-ops, still in progress and not merged to
# main (mul done, div open), and the finished feature/subtract started off it.
# Run by evals.run.prepare_fixture.
set -e
git checkout -q -b feature/calc-ops
D=docs/10_features/2026_11_10_calc_ops
mkdir -p "$D"
cat > "$D/spec.md" <<'SPEC'
# Calc operations

## Goal

`calc` grows the remaining arithmetic operations.

## Implementation plan

1. Add `mul(a, b)` to `calc.py`, with a unit test. Done.
2. Add `div(a, b)` to `calc.py`, raising `ZeroDivisionError` on zero, with a
   unit test. Not started.
3. Add `sub(a, b)`: split into its own sub-feature, `subtract`.
SPEC
git add -A
git commit -q -m "docs: add spec for calc ops"
cat >> calc.py <<'CODE'


def mul(a, b):
    return a * b
CODE
python3 - <<'PY'
p = "tests/test_calc.py"
s = open(p).read()
s = s.replace("from calc import add", "from calc import add, mul")
s = s.replace('\n\nif __name__', '''

class MulTest(unittest.TestCase):
    def test_mul(self):
        self.assertEqual(mul(3, 4), 12)


if __name__''')
open(p, "w").write(s)
PY
git add -A
git commit -q -m "feat: add mul to calc"
bash "$(dirname "$0")/../unittest-feature-done/setup.sh"
