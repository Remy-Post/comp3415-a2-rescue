# AI-Use Record (COMP 3415 A2)

AI tool used: **Claude (Anthropic), claude.ai**, one conversation on 2026-11-03.
Instructor confirmed in class that AI use is permitted for this assignment.

Full conversation (shared link): _add link here_

## How AI was used

| Area | What the AI did | Verification |
|------|-----------------|------------------|
| Understanding the code | Read through `service.py`, `menu.py`, `cli.py`, `storage.py` with me and pointed out suspected defects | Each suspected defect reproduced by running it before being reported; 3 confirmed (report Section 2) |
| Tests | Drafted `tests/test_service.py` and `tests/test_interfaces.py` | Expected values taken from `FUNCTIONAL_SPEC.md`; suite run on the untouched starter code so every failure traces to a spec rule, not a bad test |
| Refactoring | Suggested and drafted the three refactorings | Ran the full suite after each commit (same 33 pass / 3 fail as baseline) and diffed CLI output with `tools/cli_snapshot.sh` (no differences) |
| Defect fixes | Drafted the three fixes | Each fix turns exactly one failing test green; CLI diff shows only the expected discount change |
| Report | Drafted the report text | I reviewed and edited it; file/method/commit references checked against the repo |

## Task 6 – the three recommendations

### 1. Merge the duplicated code in `quote()` / `place_order()`

**AI said:** Combine `quote()` and `place_order()` in `service.py` by moving the shared validation and pricing into one private method that both call, so the pricing rules exist in only one place.

**Decision:** ACCEPT

**Why:** The two methods were ~45 identical lines. The spec says quotes and orders must price identically, and with two copies a future change could easily update only one of them.

**Evidence:** Commit `2b8441a`. Test results identical to baseline (`evidence/01-baseline.txt` vs `evidence/02-after-refactoring.txt`), `PreservedBehaviourTests.test_quote_matches_placed_order` passes, CLI snapshot diff empty (`evidence/02-cli-diff.txt`).

### 2. Change `>` to `>=` while replacing magic numbers

**AI said:** While replacing the magic numbers, also change `subtotal > 5000` to `subtotal >= STUDENT_DISCOUNT_THRESHOLD_CENTS`, since the spec says the discount applies at "at least 5,000 cents."

**Decision:** MODIFY

**Why:** The AI was right that it's a defect (`BoundaryTests.test_student_discount_applies_at_exactly_5000` fails on the starter code: discount 0 instead of 500). But putting a behaviour change inside a refactoring commit breaks the rule that a refactoring keeps behaviour the same, and it would hide the fix inside an unrelated change.

**What I did:** Kept `>` in the constants refactoring (`9d38113`, test still fails, as expected) and fixed it alone in `08655ff`. After that commit the CLI diff shows exactly one changed quote (`evidence/03-cli-diff.txt`).

### 3. Merge duplicate product lines to fix the stock check

**AI said:** To fix the duplicate-line stock problem (`hoodie:3` + `hoodie:3`), merge duplicate product lines into a single line (`hoodie:6`) before validating, and return the merged line in the quote/order.

**Decision:** REJECT

**Why:** `FUNCTIONAL_SPEC.md` says "Duplicate product lines may remain separate in the results." Merging would change the output that users and stored orders already rely on, which is more than the defect needs. Only the stock *check* was wrong.

**Evidence / what I did:** Added `_check_combined_stock()` (`6be1c8d`), which totals quantities per product without changing the lines. `test_duplicate_lines_cannot_exceed_combined_stock` now passes, and `test_quote_matches_placed_order` still sees 3 separate lines.
