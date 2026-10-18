# QuoteShot - Merge of the 2026-10-18 improvement lanes

Merger: subagent, 2026-10-18. Pristine tree `~/workspace/quoteshot/`
was never edited. Lanes applied in order: harden, then polish, then
deepen. Nothing pushed. Python stdlib only; no version bump
(pyproject still 0.1.0).

## Test counts

Test command (run in each tree): `python3 -m pytest -q`

- Baseline (pristine): 61 passed, 0 failed
- Harden lane: 104 passed (61 baseline + 43 new in tests/test_harden.py)
- Polish lane: 61 passed (no new tests, no regressions)
- Deepen lane: 77 passed (61 baseline + 16 new in tests/test_deepen_check.py)
- Merged: **120 passed, 0 failed**

Merged count equals baseline + harden additions + deepen additions
exactly (61 + 43 + 16 = 120); no deviation to explain.

Acceptance check: a pristine copy was built at the same depth as
merged/ (`../pristine-check/`) and run with the same command: 61
passed, 0 failed. The merged failure set (empty) is therefore a
subset of the pristine failure set (empty).

## Multi-lane files and how each conflict was resolved

### Harden + polish (docstrings vs code fixes; no textual overlap)

For all five files below, the harden version was copied in first,
then the polish lane's pristine-to-polish diff was applied on top.
Each result was verified both ways: merged-vs-harden shows exactly
the polish changes, and merged-vs-polish shows exactly the harden
changes. No line from either lane was dropped.

- `src/quoteshot/job.py`: harden validation/structure/all-or-nothing
  photo fixes kept in full; polish docstrings added, including the
  expanded `totals` docstring replacing the one-line summary directly
  above harden's rewritten `totals` body (both survive).
- `src/quoteshot/money.py`: harden `parse_decimal` finite/magnitude
  gate kept; polish `money()` docstring added.
- `src/quoteshot/photos.py`: harden EXIF zero-denominator and GPS
  range fixes kept; polish expanded `describe_photo` docstring added.
- `src/quoteshot/pricebook.py`: harden validation and blank-field
  guards kept; polish docstrings added, including on `empty_book` and
  `normalise_item` where harden added guard code directly under the
  new docstring (both survive in that order).
- `src/quoteshot/render.py`: harden wide-context `_pct` fix kept;
  polish docstrings for `render_text` / `render_html` / `render_job`
  added.

### Polish + deepen

- `src/quoteshot/cli.py`: polish version taken as the base (expanded
  help, docstrings, and the pricebook-help fix, all preserved).
  Deepen's changes were then added onto it: the
  `quoteshot check <job-dir>` line in the module docstring command
  map, `from .check import check_job`, and `cmd_check` copied
  verbatim from the deepen lane, inserted before `cmd_render`.
  The subparser registration is the one piece of merger-authored
  glue (see below): deepen's plain `add_parser` call was restyled to
  the polish parser conventions so `check --help` matches the other
  subcommands; the help string itself is deepen's verbatim.
- `README.md`: polish rewrite taken as the base. Deepen's content
  was hand-merged in: workflow step 6 (`quoteshot check my-job`
  after render; lead-in changed from "Five steps" to "Six steps"),
  a `check` row in the command cheat sheet, deepen's "Checking a job
  before you send the quote" section inserted verbatim after the
  cheat sheet, a table-of-contents entry for that section, and a
  short note under the exit-code table stating that for `check`,
  exit 1 means problems or drift were found and the quote is
  unchanged. All polish sections, totals, and walkthroughs are
  otherwise untouched.

### Single-lane files (copied outright)

- Harden only: `tests/test_harden.py` (new).
- Polish only: `examples/README.md`, `src/quoteshot/__init__.py`,
  `src/quoteshot/__main__.py`.
- Deepen only: `src/quoteshot/check.py` (new),
  `tests/test_deepen_check.py` (new).

## Merger-authored code

Nearly none. The only merger-authored code/text is integration glue,
marked here:

1. In `src/quoteshot/cli.py`, the `check` subparser registration
   (formatter_class, help, and a description paragraph built from
   deepen's own help text and check semantics), written to match the
   polish lane's parser style. `cmd_check`, the import, and the
   docstring command-map line are deepen's verbatim.
2. In `README.md`, the connective edits listed above (step count,
   TOC entry, cheat-sheet row, exit-code note). Deepen's new section
   text itself is verbatim.

No other merger-authored code. No lane file's logic was rewritten.

## Flags

- None. No unresolvable conflicts; no harden fix was dropped or
  weakened in any multi-lane file (verified by the two-way diffs
  described above).
- Interaction note (not a flag): deepen's `check.py` validates items
  through the shared `parse_decimal`, so in the merged tree it also
  benefits from harden's finite/magnitude gate; all 16 deepen tests
  pass against the hardened gate.
- Lane watch items carried over unchanged: polish noted the shipped
  sample job renders without the SAMPLE banner when copied without
  its price book beside it (pre-existing, not fixed by any lane);
  harden noted stored GPS from corrupt EXIF is not migrated.
- All lane `IMPROVE.md` files were removed from merged/; this
  MERGE.md is the only new file at the merged root.
