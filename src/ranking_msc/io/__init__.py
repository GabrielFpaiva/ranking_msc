"""Funções de I/O do projeto ranking_msc."""

from ranking_msc.io.ref_loader import load_dominios_fr, load_pcasp
from ranking_msc.io.snapshot_store import read_scoring_metadata, read_snapshot

__all__ = [
    "load_dominios_fr",
    "load_pcasp",
    "read_snapshot",
    "read_scoring_metadata",
]
