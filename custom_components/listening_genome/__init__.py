"""
Listening Genome — a listening-taste profile for Home Assistant.

Phase 1 of the extraction from the Music Assistant fork: the parts of the feature that never
needed Music Assistant are here and tested, with nothing from Home Assistant yet either. The
integration entry points (``async_setup_entry``, the config flow, the websocket API, the panel
and the sensors) arrive in phase 2; until then this package is plain async Python.
"""

from __future__ import annotations
