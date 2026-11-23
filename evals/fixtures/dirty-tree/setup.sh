# The finished feature branch of unittest-feature-done, plus two uncommitted
# changes: an edited tracked file and an untracked scratch file (the contents
# checks.dirty_preserved expects). Run by evals.run.prepare_fixture.
set -e
bash "$(dirname "$0")/../unittest-feature-done/setup.sh"
echo "TODO: mention sub() once the API settles" >> README.md
echo "half-written thoughts, not for commit" > scratch_notes.txt
