"""Embedding provider implementation supporting real OpenRouter API and local SentenceTransformers."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Protocol
from dotenv import load_dotenv

# Load .env from starter/ or parent directory
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Production embedder supporting OpenRouter API (qwen3-embedding-8b) with fallback to local multilingual."""

    def __init__(self, model_name: str | None = None) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        env_model = os.getenv("EMBEDDING_MODEL")
        
        if model_name:
            self.model_name = model_name
        elif env_model:
            self.model_name = env_model
        else:
            self.model_name = "qwen/qwen3-embedding-8b"

        self.use_api = bool(self.api_key and not self.api_key.startswith("your_"))
        self.local_model = None

        if self.use_api:
            print(f"[Embedder] Using OpenRouter API with model: {self.model_name}", flush=True)
            # Test embedding to determine dimensions
            sample = self._call_api(["Khởi tạo embedding"])
            self.dimensions = len(sample[0])
            print(f"[Embedder] Initialized API Embedder: {self.model_name} (dimensions={self.dimensions})", flush=True)
        else:
            print("[Embedder] No API key detected; falling back to local SentenceTransformers.", flush=True)
            from sentence_transformers import SentenceTransformer
            self.model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            self.local_model = SentenceTransformer(self.model_name)
            self.dimensions = self.local_model.get_sentence_embedding_dimension()
            print(f"[Embedder] Initialized Local Embedder: {self.model_name} (dimensions={self.dimensions})", flush=True)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call OpenRouter Embeddings endpoint with retry."""
        url = "https://openrouter.ai/api/v1/embeddings"
        payload = json.dumps({"model": self.model_name, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    embeddings = [item["embedding"] for item in data["data"]]
                    return embeddings
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2)

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Compute dense vector embeddings for documents."""
        if not texts:
            return []

        if self.use_api:
            all_embeddings = []
            total_batches = (len(texts) + batch_size - 1) // batch_size
            for idx, i in enumerate(range(0, len(texts), batch_size)):
                batch = texts[i:i + batch_size]
                print(f"  -> [Embedding] Processing batch {idx + 1}/{total_batches} ({len(batch)} chunks)...", flush=True)
                emb_batch = self._call_api(batch)
                all_embeddings.extend(emb_batch)
            return all_embeddings
        else:
            embeddings = self.local_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=True,
                normalize_embeddings=True
            )
            return embeddings.tolist()

    def embed_query(self, question: str) -> list[float]:
        """Compute query vector compatible with document vectors."""
        if self.use_api:
            return self._call_api([question])[0]
        else:
            vec = self.local_model.encode([question], normalize_embeddings=True)
            return vec[0].tolist()
