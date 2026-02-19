"""Hybrid search across all memory tiers.

Combines:
  - BM25 keyword search (exact tokens, IDs, code symbols)
  - Vector semantic search (paraphrase-tolerant)
  - Graph traversal (entity relationships, temporal queries)
  - Temporal decay (recent memories weighted higher, 30-day half-life)
  - MMR re-ranking (diversity to avoid redundant results)
"""
