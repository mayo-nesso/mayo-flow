"""Run the tests of one directory and print {test id: passed} as JSON.

Used by the `hidden_tests` fact kind (evals/checks.py) in a subprocess with
cwd = the trial's repo, so agent code that hangs or crashes cannot take the
eval runner down. Only the last stdout line is the result.
"""
import io
import json
import sys
import unittest


def discover(directory):
    """Every test in `directory` (test_*.py), as a flat list."""
    def flat(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flat(t)
            else:
                yield t
    return list(flat(unittest.TestLoader().discover(directory)))


class _Outcome(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.passed = set()

    def addSuccess(self, test):
        self.passed.add(test.id())


def main(directory):
    tests = discover(directory)
    result = _Outcome()
    unittest.TestSuite(tests).run(result)
    print(json.dumps({t.id(): t.id() in result.passed for t in tests}))


if __name__ == "__main__":
    main(sys.argv[1])
