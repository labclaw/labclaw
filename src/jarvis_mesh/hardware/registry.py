"""Device registry — discovery, state tracking, and capability declaration.

Each device self-registers via the Gateway with:
  - Identity (type, model, location)
  - Capabilities (observe, control, data formats)
  - Current state (online/offline/error/calibrating/in-use/reserved)
"""
