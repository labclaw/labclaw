"""Domain plugin package — one sub-package per scientific domain.

Each domain plugin implements the :class:`~labclaw.plugins.base.DomainPlugin`
protocol and registers itself with the global plugin_registry on import.

Built-in domains
----------------
- ``generic``      — fallback with no domain-specific logic
- ``neuroscience`` — animal subjects, fluorescence sentinels, neuro hypotheses
"""

from __future__ import annotations
