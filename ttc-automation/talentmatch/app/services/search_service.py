"""Search service — unified search across candidates and jobs"""
from __future__ import annotations
from typing import List


class SearchService:
    def __init__(self, storage):
        self.storage = storage

    def search_candidates(self, query: str, limit: int = 10) -> List[dict]:
        return self.storage.search_candidates(query, limit)

    def search_jobs(self, query: str, limit: int = 10) -> List[dict]:
        return self.storage.search_jobs(query, limit)

    def search_all(self, query: str, limit: int = 10) -> dict:
        return {
            "candidates": self.search_candidates(query, limit),
            "jobs": self.search_jobs(query, limit),
        }
