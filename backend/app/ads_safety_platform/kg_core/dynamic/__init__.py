# KG Core Dynamic Update Module

from .incremental_updater import IncrementalEngine
from .version import VersionManager, AttrVersion
from .diff import DeltaGraph, DiffSet, compute_delta

__all__ = [
    "IncrementalEngine",
    "VersionManager",
    "AttrVersion",
    "DeltaGraph",
    "DiffSet",
    "compute_delta",
]