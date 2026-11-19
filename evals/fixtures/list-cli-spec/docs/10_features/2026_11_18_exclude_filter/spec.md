# Exclude filter for the list command

## Goal

`listcli list` can hide entries that carry unwanted tags, next to the
existing `--tag` filter.

## Decisions

- A repeatable `--exclude-tag TAG` flag. An entry is hidden if it carries any
  of the given tags.
- It combines with `--tag`: the entry must match `--tag` and carry none of the
  excluded tags.
- An unknown excluded tag is not an error: it simply hides nothing.
- An empty result prints nothing and exits 0.
- Matching stays case-sensitive, like `--tag`.

## Implementation plan

1. Store: `filter_entries(entries, tag=None, exclude_tags=())` drops entries
   carrying any excluded tag; unit tests on `data.json`.
2. CLI: add the repeatable `--exclude-tag` flag to `list` and pass it to the
   store; CLI tests for one and for several excluded tags.
3. Combination: `--tag` together with `--exclude-tag`; tests for overlapping
   and disjoint cases.
4. Edge cases: unknown tag hides nothing, empty result prints nothing and
   exits 0; tests for both.
5. README: document the flag with one example.

## Test cases

- `--exclude-tag dairy` lists rice and salt.
- `--exclude-tag dairy --exclude-tag spice` lists rice.
- `--tag pantry --exclude-tag spice` lists rice.
- `--exclude-tag nope` lists all four entries.
- `--tag dairy --exclude-tag fridge` prints nothing.
