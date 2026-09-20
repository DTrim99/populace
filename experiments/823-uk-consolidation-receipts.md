# microcosm#823 consolidation receipts

## R1 — the national role rebuilds the v20 seam-built dataset bit for bit (2026-09-20)

Comparison run: `tools/build_uk_rowwise_candidate.py --release-role national` on the
v20 inputs — spine-s (`4d9752fdcd92…`, 175,920,391 bytes), Chronicle feed
`c5e5bf8` (facts `6d039dd869dc…`, manifest `20ac5d22e7d8…`), the committed feed
pin — under the ruled doctrine (1,500 epochs, `family_equal`, learning rate 0.02,
seed 0) with no solve flags, `--staging-local-only`; code = the B3 tip plus the
signed self-employment 20-30k deferral (`90bdb809`, cherry-picked as `3828183c`,
`git_dirty` false, engine 2.98.0). Output
`data/ukds/acceptance/823-consolidation/national-v20-twin/` (attempt id in its
build record). Reference: `runs/uk-623-first-calibrated/spine-assessment-v20/`
(`uk-frs-calibration-attempt-20260918T174754Z-3f928f19`, built by the retired
`tools/calibrate_uk_national_dataset.py` with `--epochs 1500
--target-weight-rule family_equal`).

- Household weights: `numpy.array_equal` on 52,846 households — **equal**.
- `calibration_diagnostics.json`: 638 target rows (name, target, initial and
  final estimate, relative error) — **equal**; final loss 0.010414168864537107,
  initial loss 0.3009223937988281, ESS 9,304.74, within-10 % 96.39 %, realized
  max weight ratio 10.0 — **equal**.
- Register: 705 compiled, 67 excluded, 638 calibrated, version `f536021bbcd9` —
  **equal**.
- Build record: `calibration` block, `input_posture`, `spine_provenance`,
  `run_config.ledger`, `run_config.doctrine` — **equal**; six calibration-seam
  gates all `passed` on both; `run_config.doctrine_overrides` is `{}` on the
  twin where v20 carried `{epochs 256 → 1500, target_weight_rule uniform →
  family_equal}` (the constants moved in B1).
- Wall time 456 s (v20: 852 s on a loaded machine), peak RSS 9.3 GB.

Rowwise manifest: `uk_national_calibrated_candidate`, `release_role national`,
`release_id microcosm-uk-2024-25-national`, `staged_dataset.status skipped`
(local-only), `staging_delivery.mode local_only`; frozen
`national_target_registry.json` version `f536021bbcd9`.

## R2 — the same build with remote staging and read-back (2026-09-20)

Same inputs, code and doctrine as R1, remote staging on at the driver's default
300 s cadence with `--staging-read-back`; output
`data/ukds/acceptance/823-consolidation/national-v20-twin-remote/`, attempt id
`uk-frs-calibration-attempt-20260920T170811Z-ce339e7c`, wall 550 s.

- Household weights and the 638 diagnostics rows equal to v20 (and to R1);
  register `f536021bbcd9`; six gates passed; `doctrine_overrides` `{}`.
- Telemetry: `policyengine/populace-uk-staging` `runs/<attempt id>/` holds
  `run_manifest.json`, `progress.json` (status `completed`), `events.ndjson`,
  `calibration_progress.json`, `artifacts/fit_summary.json`,
  `artifacts/staged_dataset.json`; `staging_delivery` in both the build record
  and the manifest: mode `local_and_remote`, 35 attempts / 35 successes,
  `read_back passed`, no error code; no telemetry warning in the run log.
- Bundle: `policyengine/populace-uk-private` `staged/<attempt id>/` (revision
  `40439a3f…`) holds the five outputs (`microcosm_uk_2024_25.h5` 176,040,337
  bytes, `build_record.json`, `calibration_diagnostics.json`,
  `microcosm_uk_2024_25.terminal_gates.json`, `national_target_registry.json`),
  the manifest, `staged_manifest.json` and `sha256sums.txt`, in one commit;
  `staged_dataset.status uploaded`.
- `tools/fetch_uk_staged_dataset.py --run-id <attempt id>` returned every file
  digest-verified and the fetched H5 is byte-equal to the local one (the copy
  was deleted after the check).

## R3 — certification of the cut (not run)

The plan's step 3 scores the candidate against the eFRS 1.57.3 copy on the run's
frozen register with `tools/score_uk_national_candidate.py`. That scorer refuses
a register it cannot materialize on both sides, and 119 of the 638 targets are
unresolvable on the incumbent (the v20 head-to-head used the evaluation repo's
pass-2 scorer, which prunes them, receipted in its run). A repository-native
certification of a national cut therefore still needs a reviewed common
register or a pruning scorer in this repository; certification, assembly and
the inspect publication wait on that (and on María's go for anything that
reaches `releases/`).
