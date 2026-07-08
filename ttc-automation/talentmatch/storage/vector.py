"""Vector search via ChromaDB — optional enhancement layer on top of SQLite"""
from __future__ import annotations
import os
from typing import List, Optional
from loguru import logger


class VectorSearch:
    """ChromaDB wrapper for candidate/job vector search. Graceful fallback."""

    def __init__(self, persist_dir: str = "", host: str = "", port: int = 0):
        self._client = None
        self._disabled = False
        self.persist_dir = persist_dir
        self.host = host
        self.port = port

    def _get_client(self):
        if self._disabled:
            return None
        if self._client is None:
            try:
                import chromadb
                if self.host and self.port:
                    self._client = chromadb.HttpClient(host=self.host, port=self.port)
                    logger.info(f"ChromaDB server: {self.host}:{self.port}")
                elif self.persist_dir:
                    os.makedirs(self.persist_dir, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=self.persist_dir)
                    logger.info(f"ChromaDB persistent: {self.persist_dir}")
                else:
                    self._client = chromadb.Client()
                    logger.info("ChromaDB in-memory mode")
            except Exception as e:
                logger.warning(f"ChromaDB init failed, vector search disabled: {e}")
                self._disabled = True
                return None
        return self._client

    def upsert_candidate(self, cid: str, data: dict):
        client = self._get_client()
        if not client:
            return
        try:
            collection = client.get_or_create_collection("candidates")
            text = " ".join(filter(None, [
                data.get("name", ""), data.get("current_role", ""),
                data.get("current_company", ""),
                data.get("skills", "") if isinstance(data.get("skills"), str) else " ".join(data.get("skills", [])),
                data.get("summary", ""),
            ]))
            if len(text.strip()) > 5:
                collection.upsert(
                    ids=[cid],
                    documents=[text],
                    metadatas=[{"name": data.get("name", ""), "role": data.get("current_role", "")}]
                )
        except Exception as e:
            logger.warning(f"ChromaDB upsert candidate failed: {e}")

    def upsert_job(self, jid: str, data: dict):
        client = self._get_client()
        if not client:
            return
        try:
            collection = client.get_or_create_collection("jobs")
            text = " ".join(filter(None, [
                data.get("title", ""), data.get("company", ""),
                data.get("required_skills", "") if isinstance(data.get("required_skills"), str) else " ".join(data.get("required_skills", [])),
                data.get("description", ""),
            ]))
            if len(text.strip()) > 5:
                collection.upsert(
                    ids=[jid],
                    documents=[text],
                    metadatas=[{"title": data.get("title", ""), "company": data.get("company", "")}]
                )
        except Exception as e:
            logger.warning(f"ChromaDB upsert job failed: {e}")

    def search_candidates(self, query: str, limit: int = 10, getter=None) -> List[dict]:
        """Search candidates by vector similarity. `getter` is a callable to fetch full candidate by id."""
        client = self._get_client()
        if not client:
            return []
        try:
            collection = client.get_or_create_collection("candidates")
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(query_texts=[query], n_results=min(limit, count))
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            out = []
            for cid, dist in zip(ids, distances):
                if getter:
                    c = getter(cid)
                    if c:
                        c["_relevance"] = round(1 - dist, 3)
                        out.append(c)
            return out
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def search_jobs(self, query: str, limit: int = 10, getter=None) -> List[dict]:
        client = self._get_client()
        if not client:
            return []
        try:
            collection = client.get_or_create_collection("jobs")
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(query_texts=[query], n_results=min(limit, count))
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            out = []
            for jid, dist in zip(ids, distances):
                if getter:
                    j = getter(jid)
                    if j:
                        j["_relevance"] = round(1 - dist, 3)
                        out.append(j)
            return out
        except Exception as e:
            logger.warning(f"Job vector search failed: {e}")
            return []

    def delete_candidate(self, cid: str):
        client = self._get_client()
        if not client:
            return
        try:
            collection = client.get_or_create_collection("candidates")
            collection.delete(ids=[cid])
        except Exception:
            pass
