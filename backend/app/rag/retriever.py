"""Query ChromaDB for relevant policy chunks."""
import os

import chromadb
from google import genai

from app.models.policy import PolicyChunk

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
EMBEDDING_MODEL = "gemini-embedding-001"


class PolicyRetriever:
    def __init__(self):
        self._chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        self._collection = self._chroma_client.get_collection("policies")
        self._genai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def retrieve(self, query: str, top_k: int = 5, plan_filter: str | None = None) -> list[PolicyChunk]:
        """Retrieve top-k relevant policy chunks for a query."""
        # Embed the query using Gemini
        response = self._genai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[query],
        )
        query_embedding = response.embeddings[0].values

        # Build where filter if plan specified
        where = None
        if plan_filter:
            where = {"source": f"{plan_filter}_roadside_policy.pdf"}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )

        chunks = []
        for i in range(len(results["ids"][0])):
            chunks.append(PolicyChunk(
                text=results["documents"][0][i],
                source=results["metadatas"][0][i]["source"],
                page=results["metadatas"][0][i]["page"],
                chunk_id=results["ids"][0][i],
                score=1 - (results["distances"][0][i] if results["distances"] else 0),
            ))
        return chunks
