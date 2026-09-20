"""Parity twin: the retiring seam command and the driver's national role.

Both paths call ``run_uk_calibration`` with the same doctrine on the same
synthetic frame and register (seed 0, five epochs, no staging), so the
calibrated household weights, the diagnostics rows and the seam-shaped build
record must agree exactly. The receipt is what licenses retiring
``tools/calibrate_uk_national_dataset.py`` (microcosm#823 B3); this module
retires with it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from microcosm.build.uk_runtime import calibration_run
from microcosm.build.uk_runtime.ledger_targets import UKLedgerTargetCompilation
from microcosm.build.uk_runtime.national_frame import (
    load_uk_national_frame,
    write_uk_national_frame,
)

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_SEAM_TESTS = _load_module(
    "uk_calibration_run_fixtures", _TESTS / "test_uk_calibration_run.py"
)
_CANDIDATE_TESTS = _load_module(
    "uk_rowwise_candidate_fixtures", _TESTS / "test_uk_rowwise_candidate.py"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stub_inputs(module, monkeypatch, *, registry, ledger_dir: Path):
    from microcosm.build.uk_runtime.chronicle_feed import load_uk_chronicle_feed

    pin = load_uk_chronicle_feed()
    artifact = SimpleNamespace(
        facts=None,
        facts_sha256=pin.facts_sha256,
        manifest_sha256=pin.manifest_sha256,
        path=ledger_dir,
        provenance=lambda: {
            "facts_sha256": pin.facts_sha256,
            "manifest_sha256": pin.manifest_sha256,
            "artifact_id": "synthetic-parity-fixture",
        },
    )
    monkeypatch.setattr(
        module, "load_ledger_consumer_artifact", lambda *args, **kwargs: artifact
    )
    monkeypatch.setattr(
        module,
        "compile_uk_target_registry",
        lambda facts, target_period: UKLedgerTargetCompilation(registry, ()),
    )
    monkeypatch.setattr(module, "load_uk_calibration_measure_exclusions", lambda p: ())
    monkeypatch.setattr(
        module,
        "apply_uk_calibration_measure_exclusions",
        lambda reg, exclusions: (reg, {}),
    )
    monkeypatch.setattr(module, "UKMeasureResolver", lambda **kwargs: None)
    return pin


def _weights(path: Path) -> np.ndarray:
    frame, _provenance = load_uk_national_frame(path)
    return np.asarray(frame.weights_for("household").values, dtype=np.float64)


def _diagnostics_rows(path: Path) -> list[tuple]:
    payload = json.loads(path.read_text())
    return [
        (
            row["name"],
            row["target"],
            row["initial_estimate"],
            row["final_estimate"],
            row["relative_error"],
        )
        for row in payload["targets"]
    ]


def test_uk_seam_command_and_national_role_agree_bit_for_bit(monkeypatch, tmp_path):
    pytest.importorskip("tables")
    monkeypatch.setenv(
        "MICROCOSM_UK_TERMINAL_GATE_SIGNING_KEY", _SEAM_TESTS.SIGNING_KEY
    )
    monkeypatch.setattr(
        calibration_run,
        "uk_aggregate_admin_totals",
        lambda frame, manifest: (_SEAM_TESTS._admin_anchor_values(), []),
    )
    frame = _SEAM_TESTS._frame()
    input_h5 = tmp_path / "spine.h5"
    write_uk_national_frame(frame, input_h5)
    _SEAM_TESTS._write_spine_sidecar(input_h5, frame)
    registry = _SEAM_TESTS._registry()
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "consumer_facts.jsonl").write_text("{}\n")
    input_sha = _sha(input_h5)

    seam = _load_module(
        "calibrate_uk_national_dataset",
        _ROOT / "tools" / "calibrate_uk_national_dataset.py",
    )
    pin = _stub_inputs(seam, monkeypatch, registry=registry, ledger_dir=ledger_dir)
    seam_out = tmp_path / "seam"
    seam_out.mkdir()
    assert (
        seam.main(
            [
                "--input-h5",
                str(input_h5),
                "--input-sha256",
                input_sha,
                "--ledger-facts",
                str(ledger_dir),
                "--ledger-facts-sha256",
                pin.facts_sha256,
                "--ledger-manifest-sha256",
                pin.manifest_sha256,
                "--staging-h5",
                str(seam_out / "microcosm_uk_2024_25.h5"),
                "--diagnostics-json",
                str(seam_out / "calibration_diagnostics.json"),
                "--build-record-json",
                str(seam_out / "build_record.json"),
                "--terminal-gate-json",
                str(seam_out / "microcosm_uk_2024_25.terminal_gates.json"),
                "--release-id",
                "dev-parity-twin",
                "--epochs",
                "5",
                "--no-staging",
            ]
        )
        == 0
    )

    builder = _CANDIDATE_TESTS._load_builder_module()
    _stub_inputs(builder, monkeypatch, registry=registry, ledger_dir=ledger_dir)
    role_out = tmp_path / "role"
    assert (
        builder.main(
            [
                "--input-h5",
                str(input_h5),
                "--release-role",
                "national",
                "--input-sha256",
                input_sha,
                "--ledger-facts",
                str(ledger_dir),
                "--ledger-facts-sha256",
                pin.facts_sha256,
                "--ledger-manifest-sha256",
                pin.manifest_sha256,
                "--out",
                str(role_out),
                "--epochs",
                "5",
                "--no-staging",
            ]
        )
        == 0
    )

    np.testing.assert_array_equal(
        _weights(seam_out / "microcosm_uk_2024_25.h5"),
        _weights(role_out / "microcosm_uk_2024_25.h5"),
    )
    assert _diagnostics_rows(seam_out / "calibration_diagnostics.json") == (
        _diagnostics_rows(role_out / "calibration_diagnostics.json")
    )
    seam_record = json.loads((seam_out / "build_record.json").read_text())
    role_record = json.loads((role_out / "build_record.json").read_text())
    assert seam_record["build_id"] != role_record["build_id"]
    assert (
        seam_record["build_id"].split("-")[:4] == role_record["build_id"].split("-")[:4]
    )
    for key in ("calibration", "gate_summary", "register", "input_posture"):
        assert seam_record[key] == role_record[key], key
    assert seam_record["spine_provenance"] == role_record["spine_provenance"]
    seam_config = dict(seam_record["run_config"])
    role_config = dict(role_record["run_config"])
    assert seam_config.pop("release_id") == "dev-parity-twin"
    assert role_config.pop("release_id") == "microcosm-uk-2024-25-national"
    assert role_config.pop("release_role") == "national"
    assert role_config.pop("rowwise_driver_parameters")["release_role"] == "national"
    assert seam_config == role_config
    assert seam_config["doctrine_overrides"] == {
        "epochs": {"default": 1500, "effective": 5}
    }
    assert seam_record["staging_delivery"] == role_record["staging_delivery"]
    seam_gates = json.loads(
        (seam_out / "microcosm_uk_2024_25.terminal_gates.json").read_text()
    )
    role_gates = json.loads(
        (role_out / "microcosm_uk_2024_25.terminal_gates.json").read_text()
    )
    assert {g: e["status"] for g, e in seam_gates["gates"].items()} == {
        g: e["status"] for g, e in role_gates["gates"].items()
    }
