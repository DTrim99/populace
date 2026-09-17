# SPM composition preflight + role for a fresh base (#893 lane)

Branch `spm-composition-preflight`, cut from `origin/main` at `d1196af10`.

## State

Scouting complete; engine rule verified at this head. Part 1 implementation
starting. Nothing pushed yet.

## Verified at this head (not inherited from the brief)

- Installed engine: `policyengine-us 2.2.1`, `spm-calculator 1.0.0`,
  `policyengine-core 3.32.5` (`.venv`, `uv sync --all-packages --locked --extra us`).
- `spm_calculator/policyengine_adapter.py:298-304` — `policyengine_amount`
  reads `spm_measurement_adults` and raises
  `SPMInputError("SPM_COMPOSITION_REQUIRED", ...)` on `np.any(adults < 1)`,
  i.e. for the whole population, not the offending unit.
- `spm_calculator/policyengine_adapter.py:353-363` —
  `spm_measurement_adults = unit.sum((age >= 18) | ((age >= 15) & role))`
  where `role` is `is_spm_independent_minor_role`.
- `spm_calculator/policyengine_adapter.py:342-350` —
  `is_spm_independent_minor_role` is a Person/ETERNITY bool whose **formula**
  is `is_household_head | is_household_spouse`. So a supplied dataset column
  wins; absent one, the formula supplies the head/spouse fallback.
- `tools/build_us_fiscal_refresh_release.py:11731` calls
  `_write_reform_validation` (defined `:7475`) with no handler.

## Done

- [x] Worktree verified at `origin/main` (`d1196af10`), venv synced.
- [x] Engine composition rule read verbatim from installed 1.0.0/2.2.1.
- [x] `release_gate_preflight.py` shape read (`CheckResult`, `PreflightReport`,
      `check_selection_carryover`, `run_preflight` SKIPPED branches).

## Next

1. Part 1.1 `check_spm_composition` in `us_runtime/release_gate_preflight.py`.
2. Part 1.2 wire into `run_preflight` + `tools/preflight_us_release_gates.py`.
3. Part 1.3 assert in `tools/build_us_fiscal_refresh_release.py`.
4. Part 1.4 `requires_us` rule-drift guard.
5. Part 1.5 tests, `tools/ci_test_groups.py --verify`, changelog, ruff.
6. Part 2 design note `docs/us-spm-role-for-a-fresh-base.md` + phase-2 measurement.
