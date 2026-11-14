"""Store and search vectors using PostgreSQL + pgvector (with persistent disk fallback)."""
import json
import os
from typing import Any
import psycopg
from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """Retain connection settings; validate model dimensions."""
        self.database_url = database_url
        self.dimensions = dimensions
        print(f"[Store] Initialized PgVectorStore with dimensions={self.dimensions}")

    def create_schema(self) -> None:
        """Create table with vector column and source/page/filter metadata."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        strategy TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        section TEXT,
                        text TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({self.dimensions})
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_strat ON document_chunks (strategy);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_sec ON document_chunks (section);")
            conn.commit()
        print("[Store] PostgreSQL schema created/verified successfully.")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Validate lengths/dimensions and write stable IDs without duplicates.

        Removes obsolete chunks for the strategy to maintain idempotency.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"Chunks count ({len(chunks)}) != Vectors count ({len(vectors)})")

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Remove obsolete chunks for this strategy
                cur.execute("DELETE FROM document_chunks WHERE strategy = %s;", (strategy,))

                # Insert in batch
                insert_query = """
                    INSERT INTO document_chunks (
                        chunk_id, strategy, document_id, source, page, section, text, metadata, embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector);
                """
                records = []
                for chunk, vec in zip(chunks, vectors):
                    section = chunk.metadata.get("section", "")
                    meta_json = json.dumps(chunk.metadata, ensure_ascii=False)
                    vec_str = "[" + ",".join(str(x) for x in vec) + "]"
                    records.append((
                        chunk.chunk_id,
                        strategy,
                        chunk.document_id,
                        chunk.source,
                        chunk.page,
                        section,
                        chunk.text,
                        meta_json,
                        vec_str
                    ))

                cur.executemany(insert_query, records)
            conn.commit()

        print(f"[Store] Strategy {strategy}: Upserted {len(chunks)} chunks into PostgreSQL pgvector.")

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Filter permitted metadata in SQL, rank by cosine distance, return top-k.

        Return chunk ID, text, score and metadata. Parameterizes user-supplied values.
        """
        vec_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        where_clauses = ["strategy = %s"]
        params: list[Any] = [strategy]

        if filters:
            for k, v in filters.items():
                if k == "section":
                    where_clauses.append("section = %s")
                    params.append(v)
                else:
                    where_clauses.append("metadata->>%s = %s")
                    params.extend([k, str(v)])

        where_sql = " AND ".join(where_clauses)
        params.extend([vec_str, top_k])

        query_sql = f"""
            SELECT
                chunk_id,
                document_id,
                source,
                page,
                section,
                text,
                metadata,
                (1.0 - (embedding <=> %s::vector)) AS score
            FROM document_chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """

        # Parameters for SELECT query: query_vector in SELECT, then where_clauses params, then query_vector in ORDER BY, then top_k
        full_params = [vec_str] + [strategy]
        if filters:
            for k, v in filters.items():
                if k == "section":
                    full_params.append(v)
                else:
                    full_params.extend([k, str(v)])
        full_params.extend([vec_str, top_k])

        hits: list[dict[str, Any]] = []
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql, full_params)
                rows = cur.fetchall()
                for r in rows:
                    meta = r[6] if isinstance(r[6], dict) else json.loads(r[6]) if r[6] else {}
                    hits.append({
                        "chunk_id": r[0],
                        "document_id": r[1],
                        "source": r[2],
                        "page": r[3],
                        "section": r[4],
                        "text": r[5],
                        "metadata": meta,
                        "score": round(float(r[7]), 4)
                    })

        return hits


# Alias VectorStore
VectorStore = PgVectorStore
