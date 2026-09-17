# US release: main builds the certified default from raw sources

## The rule

Main must demonstrably build the certified US default from raw sources and pass
its preflight and certification gates (decided 15 September 2026).

The last from-scratch build is Build P (28 July 2026, policyengine-us 1.764.6).
Every later default is a supplied-parent enrichment of that file. A pull request
large enough to change how the dataset is built carries a from-scratch build and
certification receipt from its own tree before it merges. Main carries the same
build as a standing check afterwards.

A dataset earns default status separately, by beating the incumbent on held-out
cells. Publication stays a human step: `tools/publish_release.sh` moves
`latest.json`, and only that makes a release the certified default.

## What stands between main and that build

A from-scratch attempt ran on main at `51c314382` on 15 and 16 September 2026
and reached no release. The causes below were re-read on main at `d1196af10`.
The engine lock that also blocked it is fixed: main resolves policyengine-us
2.2.1, policyengine-core 3.32.5 and spm-calculator 1.0.0.

### 1. No Chronicle feed on the build machine carries dimension labels

`_validate_chronicle_hierarchy_labels`
(`packages/microcosm-build/src/microcosm/build/ledger_targets.py:1025`) requires
exactly one Chronicle-owned label for every dimension a target selects on, and
refuses to substitute the identifier. The pinned US feed
(`consumer_facts_buildn_v9_4.jsonl`, `b3c08356…`, named in
`us/target_parity_manifest.json` and `us/target_parity_feed_families.json`)
predates those labels, so target compilation refuses in about 50 seconds on both
release arms. Every other stage waits behind this one.

Chronicle main writes the labels (`dimension_labels`, `dimension_value_labels`,
`layout.groupby_dimension_label`), and the UK feed on main is already pinned to
such an export (`uk/chronicle_feed.json`). The US needs a fresh export, the two
parity resources regenerated together with
`tools/build_us_target_parity_manifest.py`, and a `us/chronicle_feed.json` that
records the export the way the UK file does. `chronicle build-bundle` takes one
`--year`; the pinned US feed spans tax years 2020 to 2023, calendar years 2023
and 2024, and fiscal years 2026 to 2029, so the export's scope is settled before
it runs.

### 2. Nothing in the build emits the SPM independence role

In policyengine-us 2.2.1 one SPM unit with no classified adult (age 18 or over,
or age 15 or over with `is_spm_independent_minor_role`) refuses the SPM
measurement for the whole population. The release gate evaluates 104
`in_poverty` rows (`us/state_spm_poverty_levels.json`) on one whole-dataset
simulation, and `tools/build_us_fiscal_refresh_release.py` calls that after
calibration, export and the NPZ write (`_write_reform_validation`, near
`:11725`).

The certified default passes because `tools/build_us_spm_role_enrichment.py`
added the role afterwards, and that tool accepts only Build P's exact bytes
(`:117-118`). The pins record what the role does there: 28 SPM units have no
member aged 18 or over, none lacks a classified adult once the role is present
(`packages/microcosm-data/src/microcosm/data/source_enrichment.py`,
`EXPECTED_COUNTS`). A dataset built from raw sources today carries no role.

Decided 17 September 2026:

- A preflight check counts SPM units with no classified adult before the engine
  runs, and names the remedy.
- The role is delivered for a base that is not Build P.
- SPM units are never re-grouped to make the count zero. That changes the
  poverty measurement the 104 rows exist to check.
- No adult is invented where the source delivers none.

### 3. The July selection does not map onto a rebuilt base

`check_selection_carryover` (`us_runtime/release_gate_preflight.py:313`) failed
on the rebuilt base: 15,228 capital-gains own-tail donors sit on tax units the
frozen July identity list does not name
(`assert_puf_capital_gains_tail_survives_selection`,
`us_runtime/puf_capital_gains_tail.py:465`). The release tool does not require a
selection source (`--selection-source-manifest` is optional, and the reduction
at `tools/build_us_fiscal_refresh_release.py:9019` runs only when one is given).
Without one, calibration runs on the full base of about 353,000 households. The
only measured comparator is July's run on about 57,000 households: 2 hours 42
minutes at 85 GB. Nothing has been measured at full-base size.

A dataset built this way is a new lineage, not a replay of Build P: no frozen
support, a different capital-gains tail stratum, a different congressional
district assignment and a different feed identity.

`--dense-default-dataset` is diagnostic only. A release build leaves it unset,
so the default is the sparse dataset that runs on standard machines.

### 4. Three raw inputs exist in one untracked directory

The base stage reads six processed inputs. The licensed IRS public use file pair
already lives in a token-required Hugging Face repository, and the 2022 ACS rent
donor is already on the Hub. The three processed CPS ASEC files
(`census_cps_2022.h5`, `census_cps_2023.h5`, `census_cps_2024.h5`) exist only in
an untracked directory on the build machine. They derive from public Census
files. The base stage records their digests and compares them to nothing.

## Measured stage times

From the September attempt, on one 128 GiB machine, under policyengine-us
1.819.0:

| Stage | Wall time | Peak memory |
|---|---|---|
| Base from raw sources (`tools/build_us_puf_support_base.py --stage all`), machine mostly free | 46 min 28 s | 72.47 GB |
| The same under contention | 1 h 24 min 18 s | 65.10 GB |
| Preflight on the fresh base | 32.58 s | 9.76 GB |
| Target compilation, to its refusal | 49.59 s | 3.40 GB |
