"""Adapted from ../../week4/ex2_1_hybrid_search.py; see data/provenance.md.
Kept normalisation, BM25 tokenisation and weighted fusion; removed API/global
initialisation and stdout prints. Vectors are injected by the caller.
"""
from rank_bm25 import BM25Okapi

def normalise_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    low, high = min(scores), max(scores)
    if low == high:
        return [1.0] * len(scores)
    return [(score - low) / (high - low) for score in scores]

def build_bm25_index(chunks: list)-> BM25Okapi:
    return BM25Okapi([chunk.text.lower().split() for chunk in chunks])

def hybrid_search(query: str, chunks: list, vector_scores: list[float], top_k: int = 4, w_bm25: float = 0.5, w_vector: float = 0.5) -> list[tuple[int, float]]:
    if not chunks:
        return []
    if len(chunks) != len(vector_scores):
        raise ValueError("Chunk/vector count mismatch")
    bm25 = build_bm25_index(chunks)
    normalized = normalise_scores(list(bm25.get_scores(query.lower().split())))
    scores = [w_bm25 * b + w_vector * v for b, v in zip(normalized, vector_scores)]
    return sorted(enumerate(scores), key=lambda x: x[1],reverse=True)[:top_k]