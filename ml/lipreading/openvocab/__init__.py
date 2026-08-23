"""Open-vocabulary English visual speech recognition (SyncVSR, Vox+LRS2+LRS3).

Real, sentence-level, subword (unigram5000) VSR — not constrained to any fixed
vocabulary or grammar. Visual-only. MIT-licensed. See docs/open-vocabulary-*.md.
"""

from ml.lipreading.openvocab.preprocess import CropMode, OpenVocabPreprocessor

__all__ = ["CropMode", "OpenVocabPreprocessor"]
