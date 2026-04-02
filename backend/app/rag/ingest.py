"""Ingest policy PDFs: parse, chunk, embed, store in ChromaDB."""
import os
import sys

from PyPDF2 import PdfReader
import chromadb
from google import genai

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
POLICIES_DIR = os.path.join(DATA_DIR, "policies")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")

CHUNK_SIZE = 500  # characters (approx tokens for simple text)
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "gemini-embedding-001"


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text page by page from a PDF."""
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    return pages


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def ingest_policies():
    """Parse all PDFs, chunk, embed via Gemini, store in ChromaDB."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if present
    try:
        chroma_client.delete_collection("policies")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name="policies",
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks = []
    all_ids = []
    all_metadatas = []

    pdf_files = [f for f in os.listdir(POLICIES_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found in", POLICIES_DIR)
        return

    for pdf_file in pdf_files:
        pdf_path = os.path.join(POLICIES_DIR, pdf_file)
        print(f"Processing {pdf_file}...")
        pages = extract_text_from_pdf(pdf_path)

        for page_data in pages:
            chunks = chunk_text(page_data["text"])
            for j, chunk in enumerate(chunks):
                chunk_id = f"{pdf_file}:p{page_data['page']}:c{j}"
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "source": pdf_file,
                    "page": page_data["page"],
                })

    print(f"Embedding {len(all_chunks)} chunks...")

    # Embed in batches of 100 using Gemini embedding model
    all_embeddings = []
    for i in range(0, len(all_chunks), 100):
        batch = all_chunks[i:i + 100]
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
        )
        all_embeddings.extend([e.values for e in response.embeddings])

    collection.add(
        ids=all_ids,
        documents=all_chunks,
        embeddings=all_embeddings,
        metadatas=all_metadatas,
    )

    print(f"Ingested {len(all_chunks)} chunks into ChromaDB at {CHROMA_DIR}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    ingest_policies()
