"""Production model registry (Phase 22) + model manager (Phase 20-21).

Declares the visual-speech models the product knows about, their status
(PRODUCTION_CANDIDATE / BENCHMARK_ONLY / SEAM), open-vocabulary flag, dataset,
license, and reachable source. The manager reports whether each is installed and
never silently swaps an open-vocab model for GRID.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ml.common.config import MLConfig, get_ml_config


class ModelStatus:
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    BENCHMARK_ONLY = "BENCHMARK_ONLY"
    SEAM = "SEAM"  # architecture ready, weights on a blocked host


@dataclass
class ModelEntry:
    key: str                 # LIP_READING_MODEL value
    display_name: str
    status: str
    open_vocabulary: bool
    dataset: str
    vocabulary: str
    license: str
    source_url: str
    checkpoint_filenames: list[str] = field(default_factory=list)
    notes: str = ""

    def checkpoint_present(self, models_dir: str) -> bool:
        if not self.checkpoint_filenames:
            return False
        return all(os.path.exists(os.path.join(models_dir, f)) for f in self.checkpoint_filenames)


REGISTRY: list[ModelEntry] = [
    ModelEntry(
        key="syncvsr",
        display_name="SyncVSR (Vox+LRS2+LRS3)",
        status=ModelStatus.PRODUCTION_CANDIDATE,
        open_vocabulary=True,
        dataset="VoxCeleb2 + LRS2 + LRS3",
        vocabulary="open (SentencePiece unigram5000)",
        license="MIT (SyncVSR); ESPnet Apache-2.0",
        source_url="https://github.com/KAIST-AILab/SyncVSR/releases/download/weight-audio-v1/Vox%2BLRS2%2BLRS3.ckpt",
        checkpoint_filenames=["syncvsr_vox_lrs2_lrs3.ckpt"],
        notes="Sentence-level Conformer VSR. Production open-vocabulary model.",
    ),
    ModelEntry(
        key="lipnet",
        display_name="GRID-LipNet",
        status=ModelStatus.BENCHMARK_ONLY,
        open_vocabulary=False,
        dataset="GRID",
        vocabulary="closed (GRID 6-word command grammar)",
        license="MIT",
        source_url="https://github.com/Fengdalu/LipNet-PyTorch",
        checkpoint_filenames=["lipnet_overlap.pt", "shape_predictor_68_face_landmarks.dat"],
        notes="Constrained-vocabulary benchmark / regression / CI model. Not for production transcription.",
    ),
    ModelEntry(
        key="avhubert",
        display_name="AV-HuBERT (LRS3)",
        status=ModelStatus.SEAM,
        open_vocabulary=True,
        dataset="LRS3 (+VoxCeleb2)",
        vocabulary="open",
        license="CC-BY-NC-4.0 (non-commercial)",
        source_url="https://dl.fbaipublicfiles.com/avhubert/  (BLOCKED by this environment's egress policy)",
        checkpoint_filenames=[],
        notes="Adapter seam ready; weights host is blocked here. Provide weights to enable.",
    ),
]

_BY_KEY = {e.key: e for e in REGISTRY}


def get_entry(key: str) -> ModelEntry | None:
    # normalise aliases
    alias = {"openvocab": "syncvsr", "open_vocabulary": "syncvsr", "grid": "lipnet"}
    return _BY_KEY.get(alias.get(key, key))


def active_entry(config: MLConfig | None = None) -> ModelEntry | None:
    config = config or get_ml_config()
    return get_entry(config.lip_reading_model)


def manager_status(config: MLConfig | None = None) -> list[dict]:
    """Report install status for every registered model (Phase 20)."""
    config = config or get_ml_config()
    md = config.models_dir
    out = []
    for e in REGISTRY:
        installed = e.checkpoint_present(md) if e.checkpoint_filenames else False
        out.append({
            "key": e.key,
            "display_name": e.display_name,
            "status": e.status,
            "open_vocabulary": e.open_vocabulary,
            "dataset": e.dataset,
            "vocabulary": e.vocabulary,
            "license": e.license,
            "source_url": e.source_url,
            "installed": "MODEL_INSTALLED" if installed else "MODEL_NOT_INSTALLED",
            "checkpoints": e.checkpoint_filenames,
            "active": e.key == (active_entry(config).key if active_entry(config) else None),
            "notes": e.notes,
        })
    return out
