from dataclasses import asdict
import numpy as np
from .api import Embedder, CONFIG
from .data import Corpus
from .hybrid import hybrid_search
from .models import Chunk, SearchArgs

def cosine(a: list[float], b: list[float])-> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimensions differ")
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a,b)/ denominator) if denominator else 0.0

def chunk_document(doc) -> list[Chunk]:
    # Phân đoạn theo dòng: tuyệt đối không cắt ngang giữa dòng công việc (task row)
    pieces, lines, count = [], [], 0
    for line in doc.content.splitlines():
        if lines and count + len(line) > CONFIG["chunk_chars"]:
            pieces.append("\n".join(lines))
            lines, count = [], 0
        lines.append(line)
        count += len(line) + 1
    if lines:
        pieces.append("\n".join(lines))
    return [Chunk(f"{doc.metadata['doc_id']}:{i}", text, doc.metadata) for i, text in enumerate(pieces)]
    
class Retriever:
    def __init__(self, corpus: Corpus, backend: str, trace = None):
        self.corpus, self.embedder = corpus, Embedder(backend, trace)
    
    def search(self, args: SearchArgs) -> dict:
        if not args.query.strip() or args.mode not in ("dense", "hybrid") or not 1 <= args.top_k <= 8:
            raise ValueError("Invalid query, retrieval mode or top_k")
        documents = self.corpus.eligible(args.project_id, args.as_of_date)
        chunks = [c for d in documents for c in chunk_document(d)]
        if not chunks:
            return {"chunks": [], "mode": args.mode}
        vectors = self.embedder.embed([c.text for c in chunks], "retrieval.passage")
        query_vector = self.embedder.embed([args.query], "retrieval.query")[0]
        scores = [cosine(query_vector, v) for v in vectors]
        ranked = hybrid_search(args.query, chunks, scores, args.top_k) if args.mode == "hybrid" else sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:args.top_k]
        selected_ids = {chunks[i].metadata["doc_id"] for i, _ in ranked}
        related = []
        for doc in documents:
            if doc.metadata["doc_id"] in selected_ids and doc.records.get("supersedes"):
                old = next(d for d in self.corpus.docs if d.metadata["doc_id"] == doc.records["supersedes"])
                related.append({**self.corpus.source(old), "superseded_by": doc.metadata["doc_id"]})
        return {"mode": args.mode, "chunks": [{**asdict(chunks[i]), "score": round(score, 5)} for i, score in ranked], "related_documents": related, "embedding_usage": self.embedder.usage}