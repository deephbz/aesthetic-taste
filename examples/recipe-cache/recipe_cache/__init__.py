"""Explicit, correctly keyed persistence for slow computation steps.

See README.md for the identity rules and their limits.
"""
from .codecs import Codec, register as register_codec
from .identity import File, Unidentified
from .store import Audit, Decision, NestedCall, Persisted, Store

__all__ = ["Audit", "Codec", "Decision", "File", "NestedCall", "Persisted", "Store",
           "Unidentified", "register_codec"]
