"""Tier C: Agent shared state — real-time coordination between agents.

Implements Letta-style shared memory blocks for multi-agent collaboration:
  - insert: append-only, concurrency-safe
  - replace: validated, prevents accidental overwrite
  - rethink: full rewrite, last-writer-wins (use carefully)
"""
