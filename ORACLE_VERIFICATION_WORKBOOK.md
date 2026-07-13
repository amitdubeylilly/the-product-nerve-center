# Oracle Verification Workbook

Purpose: close the remaining data-accuracy risk by verifying the implemented capacity rule against real Nimbus Oracle outputs.

This workbook is an execution guide plus evidence template. It does not change runtime code.

## 1. Inputs Required

Collect oracle responses for these tools:
- capacity_oracle_roster()
- capacity_oracle(engineer_id) for multiple engineers
- dependency_oracle(item_id) for representative seeds

Minimum capacity records needed to discriminate formulas:
- one record with alloc < 100 and pto > 0 and carry = 0
- one record with pto > 0 and carry > 0
- one baseline record with alloc = 100, pto = 0, carry = 0
- one zero-allocation record

## 2. Record Table (fill from oracle)

| engineer | alloc | pto | carry | available_points |
|---|---:|---:|---:|---:|
| | | | | |
| | | | | |
| | | | | |
| | | | | |

## 3. Run Formula Fitter

1. Open .log/capacity_formula_fitter.py
2. Paste records into ORACLE_RECORDS
3. Run:

python .log/capacity_formula_fitter.py

4. Save output to a file:

python .log/capacity_formula_fitter.py > .log/capacity_formula_result.txt

## 4. Decision Rule

If winner is:
- M1 multiplicative PTO, carry after: keep current assess_capacity formula.
- M2 subtractive PTO: update assess_capacity formula and corresponding tests.
- M5 carry before proration: update operation order and tests.
- no exact fit: investigate rounding/base constant assumptions with additional oracle probes.

## 5. Dependency Rule Validation Checklist

For dependency_oracle(item_id), verify:
- soft edge handling expectation
- external ETA states (date vs TBD vs null)
- transitive traversal behavior
- cycle presence/absence and path reporting expectations

## 6. Evidence to Attach

Attach to submission materials:
- filled record table
- .log/capacity_formula_result.txt output
- short rationale paragraph: why selected formula is correct
- note of any unresolved ambiguity and how it was handled

## 7. Current Status

- Formula confirmation in code is not yet oracle-proven from records stored in this repo.
- This workbook is ready; only oracle query output is needed to close the loop.
