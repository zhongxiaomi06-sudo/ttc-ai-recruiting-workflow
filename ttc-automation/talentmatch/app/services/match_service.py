"""Match service — orchestrates JD matching"""
from __future__ import annotations


class MatchService:
    def __init__(self, storage, feishu=None):
        self.storage = storage
        self.feishu = feishu
        from pipelines.match_pipeline import MatchPipeline
        self._pipeline = MatchPipeline(storage=storage, feishu=feishu)

    def match_jd(self, jd_text: str, chat_id: str = "", source: str = "api") -> list:
        return self._pipeline.match_jd(jd_text, chat_id=chat_id, source=source)
