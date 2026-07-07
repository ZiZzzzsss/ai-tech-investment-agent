"""Backward-compatible AnySearch module.

New code should import from ``src.connectors.anysearch_skill``. This wrapper is
kept so older tests and modules continue to use the cache-only connector.
"""

from src.connectors.anysearch_skill import *  # noqa: F401,F403
