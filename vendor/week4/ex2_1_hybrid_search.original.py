import os
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

from document_model import Document
from embedding_similary_helpers import batch_embed_text, cosine_similarity
from ex2_3_vector_search import VectorStore

load_dotenv()


def normalise_scores(scores: list[float]) -> list[float]:
    """Normalise a list of scores to the range [0, 1]."""
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [1.0] * len(scores)
    return [(score - min_score) / (max_score - min_score) for score in scores]


def build_bm25_index(chunks: list) -> BM25Okapi:
    """Build a BM25 index from a list of text chunks."""
    tokenized = [chunk.content.lower().split() for chunk in chunks]
    return BM25Okapi(tokenized)


def embed_text(text: str) -> list[float]:
    """Tạo embedding cho một đoạn text qua Jina API."""
    api_key = os.getenv("JINA_API_KEY")
    return batch_embed_text(
        [text], model="jina-embeddings-v3", api_key=api_key
    )[0]


def hybrid_search(
    query: str,
    bm25_index: BM25Okapi,
    embeddings: list[list[float]],
    top_k: int = 3,
    w_bm25: float = 0.5,
    w_vector: float = 0.5,
) -> list[tuple[int, float]]:
    """Hybrid search: combine BM25 (keyword) and vector (semantic) scores.

    Returns: list of (chunk_index, hybrid_score) tuples sorted descending
    """
    # BM25 scores (raw, unbounded)
    tokenized_query = query.lower().split()
    print(f"Tokenized query: {tokenized_query}")
    bm25_scores = bm25_index.get_scores(tokenized_query)
    print(f"BM25 scores: {bm25_scores}")

    # Vector scores (cosine similarity, bounded)
    query_vec = embed_text(query)
    vector_scores = [cosine_similarity(query_vec, e) for e in embeddings]

    # Normalise BM25 to [0, 1]
    bm25_norm = normalise_scores(list(bm25_scores))

    # Fuse
    hybrid = [
        w_bm25 * b + w_vector * v for b, v in zip(bm25_norm, vector_scores)
    ]

    # Sort by hybrid score descending, return top_k
    ranked = sorted(enumerate(hybrid), key=lambda x: x[1], reverse=True)[:top_k]
    return ranked  # list of (chunk_index, score)


if __name__ == "__main__":
    store = VectorStore()

    file_path = "week4/data/company_policy.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = (
            "Remote work policy allows 2 days per week from home. Employees get"
            " 15 vacation days per year. Travel expenses can be claimed up to"
            " $500."
        )

    doc = Document(
        content=content,
        metadata={"title": "Company Policy", "source": "company_policy.txt"},
    )
    store.add(doc)

    test_questions = [
        "What is the remote work policy?",
        "How many vacation days do employees get?",
        "What can I claim for travel?",
    ]

    # Trích xuất chunks và embeddings
    chunks = (
        list(store.chunks.values())
        if isinstance(store.chunks, dict)
        else list(store.chunks)
    )
    bm25_index = build_bm25_index(chunks)
    embeddings = [chunk.embedding for chunk in chunks]

    # Run test search
    for query in test_questions:
        print(f"\n=== Query: '{query}' ===")
        results = hybrid_search(
            query=query,
            bm25_index=bm25_index,
            embeddings=embeddings,
            top_k=2,
            w_bm25=0.4,
            w_vector=0.6,
        )

        for chunk_idx, score in results:
            print(f"Chunk Index: {chunk_idx} | Hybrid Score: {score:.4f}")
            #print(f"Content: {chunks[chunk_idx].content}")