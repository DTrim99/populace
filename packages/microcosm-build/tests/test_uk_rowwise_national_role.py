"""The UK rowwise driver's national release role (microcosm#823).

The national role delegates the build to the calibration seam library, so
these tests stand on the seam run suite's synthetic frame, sidecar and
register (loaded from that module) and on the candidate suite's driver
loader and fake Hub.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from microcosm.build.logbook import load_spool_rows
from microcosm.build.staging_v2 import validate_v2_bundle
from microcosm.build.uk_runtime import calibration_run
from microcosm.build.uk_runtime.calibration_run import UK_CALIBRATION_GATE_SCOPE
from microcosm.build.uk_runtime.chronicle_feed import (
    UKChronicleFeedPinError,
    load_uk_chronicle_feed,
    require_committed_uk_chronicle_feed_pin,
)
from microcosm.build.uk_runtime.national_frame import write_uk_national_frame
from microcosm.build.uk_runtime.release_identity import UK_NATIONAL_RELEASE_ID
from microcosm.calibrate import TargetRegistry

_TESTS = Path(__file__).resolve().parent


def _load_test_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _TESTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_SEAM = _load_test_module("uk_calibration_run_fixtures", "test_uk_calibration_run.py")
_CANDIDATE = _load_test_module(
    "uk_rowwise_candidate_fixtures", "test_uk_rowwise_candidate.py"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _FakeResolver:
    """Stands in for the engine-backed resolver; the seam solves the fixture
    register from the frame's own columns when the resolver is ``None``."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _national_inputs(builder, monkeypatch, tmp_path: Path, *, resolver=None):
    frame = _SEAM._frame()
    input_h5 = tmp_path / "spine.h5"
    write_uk_national_frame(frame, input_h5)
    _SEAM._write_spine_sidecar(input_h5, frame)
    registry = _SEAM._registry()
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "consumer_facts.jsonl").write_text("{}\n")
    artifact = SimpleNamespace(
        facts=None,
        facts_sha256="1" * 64,
        manifest_sha256="2" * 64,
        path=ledger_dir,
        provenance=lambda: {
            "facts_sha256": "1" * 64,
            "manifest_sha256": "2" * 64,
            "artifact_id": "synthetic-national-fixture",
        },
    )
    pin = SimpleNamespace(
        to_dict=lambda: {"facts_sha256": "1" * 64, "manifest_sha256": "2" * 64}
    )
    monkeypatch.setattr(
        builder, "load_ledger_consumer_artifact", lambda path, **kwargs: artifact
    )
    monkeypatch.setattr(
        builder,
        "require_committed_uk_chronicle_feed_pin",
        lambda facts_sha256, **kwargs: pin,
    )
    monkeypatch.setattr(
        builder,
        "compile_uk_target_registry",
        lambda facts, target_period: SimpleNamespace(registry=registry, unsupported=()),
    )
    monkeypatch.setattr(builder, "load_uk_calibration_measure_exclusions", lambda p: ())
    monkeypatch.setattr(
        builder,
        "apply_uk_calibration_measure_exclusions",
        lambda reg, exclusions: (reg, {}),
    )
    monkeypatch.setattr(
        builder,
        "UKMeasureResolver",
        (lambda **kwargs: None) if resolver is None else resolver,
    )
    monkeypatch.setattr(
        calibration_run,
        "uk_aggregate_admin_totals",
        lambda frame, manifest: (_SEAM._admin_anchor_values(), []),
    )
    monkeypatch.setenv("MICROCOSM_UK_TERMINAL_GATE_SIGNING_KEY", _SEAM.SIGNING_KEY)
    return input_h5, registry, artifact, pin


def _argv(input_h5: Path, out: Path, *extra: str) -> list[str]:
    return [
        "--input-h5",
        str(input_h5),
        "--release-role",
        "national",
        "--input-sha256",
        _sha(input_h5),
        "--ledger-facts",
        str(input_h5.parent / "ledger"),
        "--ledger-facts-sha256",
        "1" * 64,
        "--ledger-manifest-sha256",
        "2" * 64,
        "--out",
        str(out),
        *extra,
    ]


def _fake_seam_run(calls: list[dict]):
    def fake_run(**kwargs):
        calls.append(kwargs)
        paths = kwargs["paths"]
        paths.staging_h5.write_bytes(b"h5")
        paths.diagnostics_json.write_text(
            json.dumps(
                {
                    "targets": [
                        {
                            "name": "dwp.uc.households",
                            "target_name": "dwp.uc.households",
                            "relative_error": 0.05,
                        }
                    ]
                }
            )
        )
        paths.terminal_gate_json.write_text(
            json.dumps(
                {
                    "release_id": kwargs["release_id"],
                    "gates": {
                        gate: {"status": "passed"} for gate in UK_CALIBRATION_GATE_SCOPE
                    },
                }
            )
        )
        record = {
            "build_id": kwargs["build_id"],
            "spine_provenance": {"spine_gate_report": {"sha256": "f" * 64}},
            "calibration": {
                "weights": {"household_weight_kind": "calibrated"},
                "solve": {
                    "n_targets": 1,
                    "n_households": 4,
                    "initial_loss": 0.5,
                    "final_loss": 0.01,
                    "n_nonzero": 4,
                },
                "effective_sample_size": 4.0,
                "max_weight_ratio": 1.0,
                "measure_resolution": None,
            },
        }
        paths.build_record_json.write_text(json.dumps(record))
        return SimpleNamespace(
            build_record_sha256=_sha(paths.build_record_json), build_record=record
        )

    return fake_run


def test_uk_national_role_delegates_to_the_seam_library(monkeypatch, tmp_path):
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, registry, artifact, pin = _national_inputs(
        builder, monkeypatch, tmp_path, resolver=_FakeResolver
    )
    calls: list[dict] = []
    monkeypatch.setattr(builder, "run_uk_calibration", _fake_seam_run(calls))
    out = tmp_path / "national"

    assert builder.main(_argv(input_h5, out, "--no-staging")) == 0

    call = calls[0]
    assert call["build_id"].startswith("uk-frs-calibration-attempt-")
    assert call["paths"].input_h5 == input_h5
    assert call["paths"].staging_h5 == out / "microcosm_uk_2024_25.h5"
    assert call["paths"].diagnostics_json == out / "calibration_diagnostics.json"
    assert call["paths"].build_record_json == out / "build_record.json"
    assert (
        call["paths"].terminal_gate_json
        == out / "microcosm_uk_2024_25.terminal_gates.json"
    )
    # The role's doctrine, with no overrides: the seam's own constants.
    doctrine = call["doctrine"]
    assert (doctrine.epochs, doctrine.learning_rate, doctrine.seed) == (1500, 0.02, 0)
    assert doctrine.target_weight_rule == "family_equal"
    assert call["doctrine_overrides"] == {}
    assert call["release_id"] == UK_NATIONAL_RELEASE_ID
    assert call["register_registry"] is registry
    assert call["band_edge_registry"] is registry
    assert call["calibration_year"] == 2025
    assert call["exclusion_receipt"] == {}
    assert call["ledger_artifact"] is artifact
    # The seam's direct_h5 resolver: the input file, never a live frame.
    resolver = call["measure_resolver"]
    assert isinstance(resolver, _FakeResolver)
    assert resolver.kwargs["simulation_source"] == input_h5
    assert resolver.kwargs["frame"] is None
    assert resolver.kwargs["year"] == 2025
    assert call["source_pins"]["input_h5"]["sha256"] == _sha(input_h5)
    assert call["source_pins"]["ledger_facts"]["sha256"] == "1" * 64
    extra = call["run_config_extra"]
    assert extra["release_role"] == "national"
    assert extra["allow_unpinned_feed"] is False
    assert extra["chronicle_feed_pin"] == pin.to_dict()
    assert extra["rowwise_driver_parameters"]["release_role"] == "national"
    assert extra["rowwise_driver_parameters"]["n_clones"] is None
    assert call["staging_delivery"]["mode"] == "disabled"
    assert call["staging_finalizer"] is None
    assert call["progress_callback"] is None

    manifest = json.loads((out / builder.MANIFEST_FILENAME).read_text())
    assert manifest["schema_version"] == 4
    assert manifest["build_kind"] == "uk_national_calibrated_candidate"
    assert manifest["release_role"] == "national"
    assert manifest["release_id"] == UK_NATIONAL_RELEASE_ID
    assert manifest["build_id"] == call["build_id"]
    assert set(manifest["outputs"]) == {
        "dataset",
        "calibration_diagnostics",
        "build_record",
        "terminal_gate_report",
        "national_target_registry",
    }
    assert manifest["outputs"]["build_record"]["sha256"] == _sha(
        out / "build_record.json"
    )
    assert manifest["solve"]["n_targets_by_kind"] == {
        "national": 1,
        "local": 0,
        "ladder": 0,
    }
    assert (
        manifest["solve"]["pool_households"] == manifest["solve"]["n_households"] == 4
    )
    assert manifest["parameters"]["n_clones"] is None
    assert manifest["parameters"]["doctrine"]["clone_count"] is None
    assert manifest["parameters"]["doctrine"]["target_weight_rule"] == "family_equal"
    assert manifest["fit"]["national_by_family"][0]["family"] == "dwp_universal_credit"
    assert manifest["gate"]["scope"] == list(UK_CALIBRATION_GATE_SCOPE)
    assert manifest["gate"]["posture"] == "calibration_seam"
    assert manifest["failing_gate_ids"] == []
    assert manifest["releasable"] is False
    assert manifest["release_posture"]["calibration_seam_gates_passed"] is True
    assert (
        manifest["release_posture"]["shippable_by"] == "tools/certify_uk_release_cut.py"
    )
    assert manifest["staged_dataset"]["status"] == "skipped"
    assert manifest["staging_delivery"]["mode"] == "disabled"
    frozen = TargetRegistry.from_json(out / "national_target_registry.json")
    assert frozen.version == registry.version

    # Explicit solve flags are receipted overrides of the seam doctrine.
    calls.clear()
    assert (
        builder.main(
            _argv(
                input_h5,
                tmp_path / "override",
                "--no-staging",
                "--epochs",
                "5",
                "--target-weight-rule",
                "uniform",
                "--target-loss-cap",
                "4",
            )
        )
        == 0
    )
    assert calls[0]["doctrine_overrides"] == {
        "epochs": {"default": 1500, "effective": 5},
        "target_loss_cap": {"default": 10.0, "effective": 4.0},
        "target_weight_rule": {"default": "family_equal", "effective": "uniform"},
    }


def _sums_verify(directory: Path) -> None:
    for line in (directory / "sha256sums.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert _sha(directory / name) == digest, name


def test_uk_national_role_builds_the_seam_evidence_and_stages_locally(
    monkeypatch, tmp_path, capsys
):
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path
    )
    out = tmp_path / "national"

    assert (
        builder.main(_argv(input_h5, out, "--staging-local-only", "--epochs", "5")) == 0
    )

    manifest = json.loads((out / builder.MANIFEST_FILENAME).read_text())
    assert json.loads(capsys.readouterr().out) == manifest
    run_id = manifest["build_id"]
    record = json.loads((out / "build_record.json").read_text())
    assert record["build_id"] == run_id
    assert record["pipeline"] == "uk-frs-calibration"
    assert record["run_config"]["release_id"] == UK_NATIONAL_RELEASE_ID
    assert record["run_config"]["release_role"] == "national"
    assert record["run_config"]["doctrine_overrides"] == {
        "epochs": {"default": 1500, "effective": 5}
    }
    assert record["run_config"]["doctrine"]["target_weight_rule"] == "family_equal"
    # The bindings the release-cut certifier reads.
    dataset = out / "microcosm_uk_2024_25.h5"
    gates = out / "microcosm_uk_2024_25.terminal_gates.json"
    diagnostics = out / "calibration_diagnostics.json"
    assert record["artifacts"]["staging_h5"]["sha256"] == _sha(dataset)
    assert record["artifacts"]["diagnostics_json"]["sha256"] == _sha(diagnostics)
    assert record["artifacts"]["terminal_gate_json"]["sha256"] == _sha(gates)
    assert record["spine_provenance"]["spine_gate_report"]["sha256"]
    assert json.loads(diagnostics.read_text())["build"]["build_id"] == run_id
    assert record["staging_delivery"]["mode"] == "local_only"
    assert record["staging_delivery"] == manifest["staging_delivery"]
    assert manifest["outputs"]["dataset"]["sha256"] == _sha(dataset)
    assert manifest["outputs"]["build_record"]["sha256"] == _sha(
        out / "build_record.json"
    )
    assert manifest["build_record"]["sha256"] == _sha(out / "build_record.json")
    assert set(manifest["gate"]["statuses"]) == set(UK_CALIBRATION_GATE_SCOPE)
    assert manifest["solve"]["n_targets"] == 1
    assert manifest["staged_dataset"]["status"] == "skipped"
    _sums_verify(out)

    bundle = validate_v2_bundle(out / "staging", run_id)
    run_manifest = bundle["run_manifest"]
    assert run_manifest["operation_id"] == "uk_national_calibration"
    assert run_manifest["pipeline"]["id"] == "uk-frs-calibration"
    assert run_manifest["run_kind"] == "calibration"
    assert bundle["progress"]["status"] == "completed"
    stage_ids = {event["stage_id"] for event in bundle["events"]}
    assert {
        "input_pinning",
        "target_compilation",
        "calibration",
        "release_check_evaluation",
        "build_record_creation",
        "dataset_staging",
        "complete",
    } <= stage_ids
    artifacts = out / "staging" / "runs" / run_id / "artifacts"
    assert (artifacts / "fit_summary.json").is_file()
    assert (artifacts / "staged_dataset.json").is_file()
    fit_summary = json.loads((artifacts / "fit_summary.json").read_text())
    assert fit_summary["build_kind"] == "uk_national_calibrated_candidate"
    assert fit_summary["fit_by_family"]["local"] == {}
    assert "dwp_universal_credit" in fit_summary["fit_by_family"]["national"]

    rows = load_spool_rows(out / "logbook-spool")
    assert len(rows) == 1
    assert rows[0].build_id == run_id
    assert rows[0].pipeline == "uk-frs-calibration"


def test_uk_national_role_publishes_telemetry_and_the_bundle_to_the_hub(
    monkeypatch, tmp_path
):
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, _registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path
    )
    hub = _CANDIDATE._FakeHub()
    monkeypatch.setattr(builder, "_hub_api", lambda: hub)
    monkeypatch.setattr(builder, "_hub_token", lambda: "hf_test_token")
    out = tmp_path / "national"

    assert (
        builder.main(
            _argv(
                input_h5, out, "--epochs", "5", "--staging-upload-interval-seconds", "0"
            )
        )
        == 0
    )

    manifest = json.loads((out / builder.MANIFEST_FILENAME).read_text())
    run_id = manifest["build_id"]
    assert run_id.startswith("uk-frs-calibration-attempt-")
    telemetry_paths = hub.paths("policyengine/populace-uk-staging")
    assert telemetry_paths == sorted(
        f"runs/{run_id}/{name}"
        for name in (
            "run_manifest.json",
            "progress.json",
            "events.ndjson",
            "calibration_progress.json",
            "artifacts/fit_summary.json",
            "artifacts/staged_dataset.json",
        )
    )
    remote_progress = json.loads(
        hub.files[("policyengine/populace-uk-staging", f"runs/{run_id}/progress.json")]
    )
    assert remote_progress["status"] == "completed"
    remote_manifest = json.loads(
        hub.files[
            ("policyengine/populace-uk-staging", f"runs/{run_id}/run_manifest.json")
        ]
    )
    assert remote_manifest["operation_id"] == "uk_national_calibration"
    delivery = manifest["staging_delivery"]
    assert delivery["mode"] == "local_and_remote"
    assert delivery["upload_successes"] == delivery["upload_attempts"] > 0
    assert delivery["last_error_code"] is None

    assert len(hub.commits) == 1
    commit = hub.commits[0]
    assert commit["repo_id"] == "policyengine/populace-uk-private"
    expected = {Path(entry["path"]).name for entry in manifest["outputs"].values()} | {
        builder.MANIFEST_FILENAME,
        "staged_manifest.json",
        "sha256sums.txt",
    }
    assert commit["paths"] == sorted(f"staged/{run_id}/{name}" for name in expected)
    assert "microcosm_uk_2024_25.h5" in expected and "build_record.json" in expected
    staged = manifest["staged_dataset"]
    assert staged["status"] == "uploaded"
    assert staged["repository"] == "policyengine/populace-uk-private"
    assert staged["prefix"] == f"staged/{run_id}"
    remote_h5 = hub.files[
        ("policyengine/populace-uk-private", f"staged/{run_id}/microcosm_uk_2024_25.h5")
    ]
    assert remote_h5 == (out / "microcosm_uk_2024_25.h5").read_bytes()
    record = json.loads((out / "build_record.json").read_text())
    assert record["staging_delivery"] == delivery


def test_uk_national_dry_run_prints_the_plan_and_writes_nothing(
    monkeypatch, tmp_path, capsys
):
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path
    )
    out = tmp_path / "national"

    assert builder.main(_argv(input_h5, out, "--dry-run")) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["build_kind"] == "uk_national_calibrated_candidate_plan"
    assert plan["release_role"] == "national"
    assert plan["release_id"] == UK_NATIONAL_RELEASE_ID
    assert plan["dry_run"] is True
    assert plan["targets"]["active"] == plan["targets"]["compiled"] == 1
    assert plan["targets"]["register_sha256"] == registry.version
    assert plan["doctrine"]["epochs"] == 1500
    assert plan["doctrine"]["target_weight_rule"] == "family_equal"
    assert plan["doctrine_overrides"] == {}
    assert plan["parameters"]["release_role"] == "national"
    assert plan["engine"] == "not_run"
    assert plan["releasable"] is False
    assert not out.exists()


def test_uk_national_role_marks_the_staging_run_failed_on_a_refusal(
    monkeypatch, tmp_path
):
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, _registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        builder,
        "compile_uk_target_registry",
        lambda facts, target_period: SimpleNamespace(
            registry=None, unsupported=("dwp.uc.households",)
        ),
    )
    out = tmp_path / "national"
    with pytest.raises(SystemExit, match="failed to compile"):
        builder.main(_argv(input_h5, out, "--staging-local-only"))
    runs = sorted(path.name for path in (out / "staging" / "runs").iterdir())
    assert len(runs) == 1
    bundle = validate_v2_bundle(out / "staging", runs[0])
    assert bundle["progress"]["status"] == "failed"
    assert not (out / "build_record.json").exists()


# --- Behaviours re-anchored from the retired seam command's tests (B3) ---


def test_uk_national_role_has_no_release_id_flag(tmp_path) -> None:
    """Canonical ids are the role's own; the seam's --release-id is gone."""

    builder = _CANDIDATE._load_builder_module()
    (tmp_path / "spine.h5").write_bytes(b"spine")
    with pytest.raises(SystemExit):
        builder._parse_args(
            _argv(tmp_path / "spine.h5", tmp_path / "out", "--release-id", "dev-x")
        )


def test_uk_national_role_accepts_operator_exclusions_and_refuses_a_bad_sha(
    tmp_path,
) -> None:
    builder = _CANDIDATE._load_builder_module()
    (tmp_path / "spine.h5").write_bytes(b"spine")
    exclusions = tmp_path / "operator.json"
    exclusions.write_text("{}", encoding="utf-8")
    argv = _argv(tmp_path / "spine.h5", tmp_path / "out")
    argv[argv.index("--input-sha256") + 1] = "0" * 64
    parsed = builder._parse_args([*argv, "--measure-exclusions", str(exclusions)])
    builder._validate_cli_args(parsed)
    assert parsed.measure_exclusions == exclusions
    argv[argv.index("--input-sha256") + 1] = "not-a-sha"
    with pytest.raises(SystemExit):
        builder._parse_args(argv)


def test_uk_national_role_exposes_the_shared_staging_modes(tmp_path) -> None:
    builder = _CANDIDATE._load_builder_module()
    (tmp_path / "spine.h5").write_bytes(b"spine")
    argv = _argv(tmp_path / "spine.h5", tmp_path / "out")
    argv[argv.index("--input-sha256") + 1] = "0" * 64
    remote = builder._parse_args(argv)
    local = builder._parse_args([*argv, "--staging-local-only"])
    disabled = builder._parse_args([*argv, "--no-staging"])
    assert remote.staging_repo_id == "policyengine/populace-uk-staging"
    assert not remote.staging_local_only and not remote.no_staging
    assert local.staging_local_only and not local.no_staging
    assert disabled.no_staging
    with pytest.raises(SystemExit):
        builder._parse_args([*argv, "--staging-repo-id", ""])
    with pytest.raises(SystemExit):
        builder._parse_args([*argv, "--staging-local-only", "--staging-read-back"])


def _foreign_artifact(ledger_dir: Path, *, facts_sha256: str, manifest_sha256):
    return SimpleNamespace(
        facts=None,
        facts_sha256=facts_sha256,
        manifest_sha256=manifest_sha256,
        path=ledger_dir,
        provenance=lambda: {
            "facts_sha256": facts_sha256,
            "manifest_sha256": manifest_sha256,
            "artifact_id": "foreign",
        },
    )


@pytest.mark.parametrize("manifest_sha256", ["c" * 64, None])
def test_uk_national_role_refuses_a_feed_outside_the_committed_pin(
    monkeypatch, tmp_path, manifest_sha256
) -> None:
    """The committed pin is checked before the register compiles."""

    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, _registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path
    )
    # The fixture stubs the check; this test wants the real one.
    monkeypatch.setattr(
        builder,
        "require_committed_uk_chronicle_feed_pin",
        require_committed_uk_chronicle_feed_pin,
    )
    pin = load_uk_chronicle_feed()
    artifact = _foreign_artifact(
        tmp_path / "ledger",
        facts_sha256=pin.facts_sha256,
        manifest_sha256=manifest_sha256,
    )
    monkeypatch.setattr(
        builder, "load_ledger_consumer_artifact", lambda path, **kwargs: artifact
    )

    def compile_must_not_run(facts, target_period):
        raise AssertionError("the register compiled before the feed pin was checked")

    monkeypatch.setattr(builder, "compile_uk_target_registry", compile_must_not_run)
    out = tmp_path / "national"
    with pytest.raises(UKChronicleFeedPinError, match="manifest: loaded"):
        builder.main(_argv(input_h5, out, "--staging-local-only"))
    # The refusal happened after telemetry opened: the local run reads failed.
    runs = sorted(path.name for path in (out / "staging" / "runs").iterdir())
    assert (
        validate_v2_bundle(out / "staging", runs[0])["progress"]["status"] == "failed"
    )


def test_uk_national_role_records_an_unpinned_feed_override(
    monkeypatch, tmp_path
) -> None:
    pytest.importorskip("tables")
    builder = _CANDIDATE._load_builder_module()
    input_h5, _registry, _artifact, _pin = _national_inputs(
        builder, monkeypatch, tmp_path, resolver=_FakeResolver
    )
    monkeypatch.setattr(
        builder,
        "require_committed_uk_chronicle_feed_pin",
        require_committed_uk_chronicle_feed_pin,
    )
    artifact = _foreign_artifact(
        tmp_path / "ledger", facts_sha256="0" * 64, manifest_sha256="c" * 64
    )
    monkeypatch.setattr(
        builder, "load_ledger_consumer_artifact", lambda path, **kwargs: artifact
    )
    calls: list[dict] = []
    monkeypatch.setattr(builder, "run_uk_calibration", _fake_seam_run(calls))
    out = tmp_path / "national"
    assert (
        builder.main(_argv(input_h5, out, "--no-staging", "--allow-unpinned-feed")) == 0
    )
    extra = calls[0]["run_config_extra"]
    assert extra["allow_unpinned_feed"] is True
    # The pin the artifact was checked against is the committed one.
    assert extra["chronicle_feed_pin"]["facts_sha256"] != "0" * 64
