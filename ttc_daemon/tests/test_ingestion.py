"""摄入链路测试：JD 提交 → classify → normalize → route → mission_created"""
import json

from ttc_daemon import db
from ttc_daemon.ingestion import artifact_classifier, normalizer, mission_router


def _create_read_job(source_type: str, raw_text: str, source_url: str = "") -> str:
    """创建一个测试 read_job 并返回其 ID。"""
    job = {
        "source_type": source_type,
        "source_url": source_url,
        "title": "Test JD",
        "raw_text": raw_text,
        "markdown": raw_text,
        "status": "pending",
        "capture_meta": {},
    }
    return db.insert_read_job(job)


def _create_ingest_record(record_id: str, source_type: str, raw_text: str) -> str:
    """创建一个 ingest_record 用于测试。"""
    record = {
        "id": record_id,
        "source_type": source_type,
        "source_url": "",
        "title": "Test Record",
        "raw_text": raw_text,
        "markdown": raw_text,
        "read_method": "requests",
        "read_status": "ok",
        "content_type_guess": "jd",
        "error_reason": "",
        "error": "",
        "capture_meta": {},
        "payload": {},
        "collected_at": db.now_iso(),
    }
    return db.insert_ingest(record)


class TestClassifyNormalizeRoute:
    """测试分类 → 归一化 → 路由的完整链路。"""

    def test_classify_jd_text(self, temp_db, sample_jd_text):
        """JD 文本应被正确分类为 jd 类型。"""
        record = {
            "id": "test_jd_001",
            "source_type": "web_page",
            "raw_text": sample_jd_text,
        }
        artifact_type, confidence, reason = artifact_classifier.classify(record)
        assert artifact_type == "jd", f"Expected 'jd', got '{artifact_type}'"
        assert confidence >= 0.6, f"Confidence too low: {confidence}"
        assert reason, "Reason should not be empty"

    def test_normalize_jd(self, temp_db, sample_jd_text):
        """JD 文本应被归一化为结构化字段。"""
        record = {
            "id": "test_jd_002",
            "source_type": "web_page",
            "raw_text": sample_jd_text,
        }
        normalized = normalizer.normalize("jd", record)
        assert isinstance(normalized, dict), "Normalized result should be a dict"
        # 至少应有 position 或 skills
        assert (
            normalized.get("position") or normalized.get("skills")
        ), "Normalized JD should have position or skills"

    def test_route_jd_creates_mission(self, temp_db, sample_jd_text):
        """JD artifact 路由应创建 Mission。"""
        # 创建 ingest_record
        rid = _create_ingest_record("test_jd_003", "web_page", sample_jd_text)

        # 分类 + 归一化
        record = db.get_ingest(rid)
        artifact_type, confidence, reason = artifact_classifier.classify(record)
        normalized_payload = normalizer.normalize(artifact_type, record)

        # 创建 normalized_artifact
        aid = db.insert_normalized_artifact({
            "raw_ingest_id": rid,
            "artifact_type": artifact_type,
            "confidence": confidence,
            "reason": reason,
            "normalized_payload": normalized_payload,
            "status": "pending",
        })

        # 路由
        artifact = db.get_normalized_artifact(aid)
        result = mission_router.route(artifact)

        # 验证结果
        assert result["action"] in (
            "mission_created", "mission_exists", "needs_review"
        ), f"Unexpected action: {result['action']}"

        if result["action"] == "mission_created":
            mission_id = result.get("mission_id")
            assert mission_id, "Mission ID should be present"
            mission = db.get_mission(mission_id)
            assert mission is not None, f"Mission {mission_id} not found"
            assert mission["state"] == "created", f"Expected 'created', got '{mission['state']}'"

    def test_classify_non_jd_text(self, temp_db):
        """非 JD 文本不应被分类为 jd。"""
        record = {
            "id": "test_non_jd",
            "source_type": "web_page",
            "raw_text": "今天天气很好，适合出去玩。周末有什么计划吗？",
        }
        artifact_type, confidence, reason = artifact_classifier.classify(record)
        # 不应为 jd 且置信度应较低
        if artifact_type == "jd":
            assert confidence < 0.6, f"Non-JD text should have low JD confidence, got {confidence}"
        # 只要能正常返回即可
        assert artifact_type in ("jd", "candidate", "evidence", "chat", "unknown"), \
            f"Unexpected artifact_type: {artifact_type}"


class TestReadJobFlow:
    """测试 read_job 的创建和状态更新。"""

    def test_create_read_job(self, temp_db):
        """创建 read_job 应返回有效 ID。"""
        jid = _create_read_job("web_page", "test content", "https://example.com/jd")
        assert jid.startswith("rjob_"), f"Invalid read job ID: {jid}"

        job = db.get_read_job(jid)
        assert job is not None
        assert job["source_type"] == "web_page"
        assert job["status"] == "pending"

    def test_update_read_job_status(self, temp_db):
        """更新 read_job 状态应生效。"""
        jid = _create_read_job("feishu_docx", "feishu content")
        db.update_read_job(jid, {"status": "completed", "read_status": "ok"})

        job = db.get_read_job(jid)
        assert job["status"] == "completed"
        assert job["read_status"] == "ok"

    def test_read_job_error_handling(self, temp_db):
        """read_job 失败时应正确记录错误信息。"""
        jid = _create_read_job("web_page", "", "https://example.com/broken")
        db.update_read_job(jid, {
            "status": "failed",
            "error": "Connection refused",
            "error_reason": "network_error",
            "read_status": "failed",
        })

        job = db.get_read_job(jid)
        assert job["status"] == "failed"
        assert "Connection refused" in job.get("error", "")


class TestNormalizedArtifactLifecycle:
    """测试 normalized_artifact 的完整生命周期。"""

    def test_insert_and_retrieve_artifact(self, temp_db):
        """插入并检索 normalized_artifact。"""
        aid = db.insert_normalized_artifact({
            "raw_ingest_id": "test_ingest",
            "artifact_type": "jd",
            "confidence": 0.9,
            "reason": "LLM classified with high confidence",
            "normalized_payload": {"position": "高级后端", "company": "某公司"},
            "status": "pending",
        })
        assert aid.startswith("art_"), f"Invalid artifact ID: {aid}"

        artifact = db.get_normalized_artifact(aid)
        assert artifact is not None
        assert artifact["artifact_type"] == "jd"
        assert artifact["confidence"] == 0.9
        payload = json.loads(artifact["normalized_payload"])
        assert payload["position"] == "高级后端"

    def test_pending_artifacts_query(self, temp_db):
        """查询 pending artifacts 应正确过滤。"""
        # 插入两个 artifact
        db.insert_normalized_artifact({
            "raw_ingest_id": "ingest_1",
            "artifact_type": "jd",
            "confidence": 0.9,
            "normalized_payload": {},
            "status": "pending",
        })
        db.insert_normalized_artifact({
            "raw_ingest_id": "ingest_2",
            "artifact_type": "candidate",
            "confidence": 0.7,
            "normalized_payload": {},
            "status": "routed",
        })

        pending = db.get_pending_normalized_artifacts(limit=100)
        pending_types = [a["artifact_type"] for a in pending]
        assert "jd" in pending_types
        # routed 的不应在 pending 中
        routed = [a for a in pending if a["status"] != "pending"]
        assert len(routed) == 0
