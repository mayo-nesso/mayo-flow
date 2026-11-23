# Builds a finished feature branch on top of a main that already has ten
# --no-ff merges and no audit report. Run by evals.run.prepare_fixture.
set -e
mkdir -p docs/50_audits/archived docs/notes
touch docs/50_audits/archived/.gitkeep
for i in 01 02 03 04 05 06 07 08 09 10; do
  git checkout -q -b "feature/note-$i"
  echo "note $i" > "docs/notes/$i.md"
  git add -A
  git commit -q -m "docs: add note $i"
  git checkout -q main
  git merge -q --no-ff -m "Merge feature/note-$i into main" "feature/note-$i"
  git branch -q -d "feature/note-$i"
done
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
