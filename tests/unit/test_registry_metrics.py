"""Unit tests: model registry, open-vocab availability honesty, S/D/I metrics."""

from __future__ import annotations

from ml.common.results import AvailabilityState
from training.evaluation import alignment_ops


def test_model_registry_declares_production_and_benchmark():
    from ml.lipreading.registry import ModelStatus, active_entry, get_entry, manager_status

    syncvsr = get_entry("syncvsr")
    lipnet = get_entry("lipnet")
    assert syncvsr.open_vocabulary is True
    assert syncvsr.status == ModelStatus.PRODUCTION_CANDIDATE
    assert lipnet.open_vocabulary is False
    assert lipnet.status == ModelStatus.BENCHMARK_ONLY
    # aliases resolve
    assert get_entry("openvocab").key == "syncvsr"
    assert get_entry("grid").key == "lipnet"

    status = manager_status()
    keys = {m["key"] for m in status}
    assert {"syncvsr", "lipnet", "avhubert"} <= keys
    for m in status:
        assert m["installed"] in ("MODEL_INSTALLED", "MODEL_NOT_INSTALLED")


def test_openvocab_unavailable_when_checkpoint_missing(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    monkeypatch.setenv("LIP_READING_MODEL", "syncvsr")
    monkeypatch.setenv("OPENVOCAB_WEIGHTS", "/nonexistent/syncvsr.ckpt")
    monkeypatch.setenv("MODELS_DIR", "/nonexistent-dir")
    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    av = get_lip_reading_model(get_ml_config()).availability()
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE
    # Names the exact reachable source rather than faking or falling back to GRID.
    assert "github.com/KAIST-AILab/SyncVSR" in (av.detail or "")
    assert av.missing


def test_openvocab_model_info_is_open_vocabulary():
    from ml.common.config import get_ml_config
    from ml.lipreading.adapters.openvocab_adapter import OpenVocabularyLipReadingModel

    info = OpenVocabularyLipReadingModel(get_ml_config()).get_model_info()
    assert info.name == "syncvsr-vox-lrs2-lrs3"
    assert "open" in info.configuration["vocabulary"].lower()


def test_alignment_ops_sub_del_ins():
    # ref: 4 words; hyp drops one and substitutes one
    ops = alignment_ops("the cat sat", "the dog sat down")
    assert ops["ref_words"] == 4
    assert ops["sub"] == 1  # dog->cat
    assert ops["del"] == 1  # down missing
    assert ops["ins"] == 0
    assert ops["hits"] == 2  # the, sat
    perfect = alignment_ops("hello world", "hello world")
    assert perfect["sub"] == perfect["del"] == perfect["ins"] == 0
