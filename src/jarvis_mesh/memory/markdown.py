"""Tier A: Human-readable memory — markdown files as source of truth.

Handles lab/SOUL.md, lab/MEMORY.md, lab/protocols/, lab/decisions/,
lab/failures/, lab/stream/, and members/*/persona.md + memory.md.

Inspired by OpenClaw's memory architecture: files are the truth,
searchable via BM25 + vector hybrid, with temporal decay.
"""
