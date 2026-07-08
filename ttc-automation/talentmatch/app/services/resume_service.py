"""Resume processing service"""
from __future__ import annotations


class ResumeService:
    """Orchestrates resume parsing and storage"""

    def __init__(self, storage, feishu=None):
        self.storage = storage
        self.feishu = feishu
        from pipelines.resume_pipeline import ResumePipeline
        self._pipeline = ResumePipeline(storage=storage, feishu=feishu)

    def process_file(self, file_path: str, chat_id: str = "", owner_id: str = "") -> dict:
        return self._pipeline.process_file(file_path, chat_id=chat_id, owner_id=owner_id)

    def process_batch(self, files: list, chat_id: str = "", owner_id: str = "") -> dict:
        return self._pipeline.process_batch(files, chat_id=chat_id, owner_id=owner_id)
