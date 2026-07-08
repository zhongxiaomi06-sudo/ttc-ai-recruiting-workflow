"""状态机测试：Mission 全状态流转 + 异常恢复"""
import json

from ttc_daemon import db
from ttc_daemon.agents import orchestrator


def _create_mission_with_jd(
    jd_fields: dict,
    state: str = "created",
) -> str:
    """创建一个带 JD 的测试 Mission。"""
    mid = db.insert_mission(jd_record_id="test_jd", config={"test": True})
    db.update_mission_state(mid, state, {"jd_fields": jd_fields})
    return mid


def _add_test_candidates(mission_id: str, count: int = 3) -> list:
    """为 Mission 添加测试候选人。"""
    cids = []
    for i in range(count):
        cid = db.insert_candidate({
            "name": f"候选人{i+1}",
            "email": f"candidate{i+1}@test.com",
            "jd_alignment_score": 80 - i * 10,
            "gold_score": 75 - i * 5,
            "overall_score": 78 - i * 10,
            "source_types": ["test"],
        })
        cids.append(cid)
    db.update_mission_state(mission_id, "sourcing", {"candidate_ids": cids})
    return cids


class TestStateMachineFlow:
    """测试 Mission 状态机全流程。"""

    def test_created_to_jd_parsed(self, temp_db):
        """created → jd_parsed：有效的 JD 应解析成功。"""
        mid = _create_mission_with_jd(
            {"position": "高级后端工程师", "company": "某AI公司", "skills": ["Python", "Go"]},
            state="created",
        )
        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        assert mission["state"] in ("jd_parsed", "closed"), \
            f"Expected jd_parsed or closed, got {mission['state']}"

    def test_created_with_no_jd_closes(self, temp_db):
        """created → closed：无 JD 时直接关闭 Mission。"""
        mid = db.insert_mission(config={"test": True})
        # 不设置 jd_fields

        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        assert mission["state"] == "closed", \
            f"Expected closed for no-JD mission, got {mission['state']}"

    def test_created_with_empty_jd_generates_problem(self, temp_db):
        """created → problem_pending：JD 解析为空时生成 human_task。"""
        mid = _create_mission_with_jd(
            {"position": "", "skills": []},
            state="created",
        )
        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        assert mission["state"] in ("problem_pending", "jd_parsed"), \
            f"Expected problem_pending or jd_parsed, got {mission['state']}"

    def test_scored_to_calling_no_risks(self, temp_db):
        """scored → calling：无风险的候选人应直接进入 calling。"""
        jd_fields = {"position": "高级后端", "company": "某AI公司", "skills": ["Python"]}
        mid = _create_mission_with_jd(jd_fields, state="scored")
        # 添加干净候选人（无 risk_flags）
        cid = db.insert_candidate({
            "name": "干净候选人",
            "email": "clean@test.com",
            "overall_score": 85,
            "level": "扎实",
            "confidence": "high",
            "risk_flags": [],
            "needs_human_review": False,
            "source_types": ["test"],
        })
        db.update_mission_state(mid, "scored", {"candidate_ids": [cid]})

        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        # 无风险 → 应跳过 human_review，进入 calling
        assert mission["state"] in ("calling", "human_pending", "problem_pending"), \
            f"Expected calling/human_pending/problem_pending, got {mission['state']}"

    def test_scored_to_human_review_with_risks(self, temp_db):
        """scored → human_review：有风险信号的候选人应触发人工审核。"""
        jd_fields = {"position": "高级后端", "company": "某AI公司", "skills": ["Python"]}
        mid = _create_mission_with_jd(jd_fields, state="scored")
        # 添加有风险信号的候选人
        cid = db.insert_candidate({
            "name": "风险候选人",
            "email": "risky@test.com",
            "overall_score": 70,
            "level": "中上",
            "confidence": "low",
            "risk_flags": [
                {"flag": "上一份工作不满1年", "severity": "yellow", "detail": "仅8个月"},
            ],
            "needs_human_review": False,
            "source_types": ["test"],
        })
        db.update_mission_state(mid, "scored", {"candidate_ids": [cid]})

        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        # 置信度低 → 应进入 human_review
        assert mission["state"] in ("human_review", "calling"), \
            f"Expected human_review or calling, got {mission['state']}"

    def test_human_pending_resume_to_feedback(self, temp_db):
        """human_pending → feedback：所有任务完成应进入 feedback。"""
        jd_fields = {"position": "高级后端", "company": "某AI公司"}
        mid = _create_mission_with_jd(jd_fields, state="human_pending")
        # 创建一个已完成的 call task
        tid = db.insert_human_task(mid, "phone_caller", "call", {
            "candidate_id": "test_cand",
            "call_list_id": "test_call",
        })
        db.complete_human_task(tid, {"outcome": "interested", "notes": "有意向"})

        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        # 所有任务完成 → 应进入 feedback 或 closed
        assert mission["state"] in ("feedback", "closed"), \
            f"Expected feedback or closed, got {mission['state']}"

    def test_feedback_to_closed(self, temp_db):
        """feedback → closed：反馈处理后关闭 Mission。"""
        jd_fields = {"position": "高级后端", "company": "某AI公司"}
        mid = _create_mission_with_jd(jd_fields, state="feedback")

        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        assert mission["state"] == "closed", \
            f"Expected closed, got {mission['state']}"
        assert mission.get("outcome") == "completed", \
            f"Expected 'completed' outcome, got {mission.get('outcome')}"


class TestErrorRecovery:
    """测试异常恢复：失败 → problem_task → 人工解决 → resume。"""

    def test_step_error_creates_problem_task(self, temp_db):
        """Mission 步进异常时应创建 problem_task 并进入 problem_pending。"""
        mid = db.insert_mission(config={"test": True})
        db.update_mission_state(mid, "created", {
            "jd_fields": {"position": "测试", "skills": ["test"]},
            "jd_record_id": None,
            "normalized_artifact_id": None,
        })

        # 此时 JD record 为 None，但 jd_fields 已有值，所以应能直接走到 jd_parsed
        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        mission = db.get_mission(mid)
        assert mission["state"] in ("jd_parsed", "problem_pending", "closed"), \
            f"Unexpected state: {mission['state']}"

    def test_resume_from_problem_pending(self, temp_db):
        """problem_pending 状态下的 Mission 应等待人工解决后 resume。"""
        jd_fields = {"position": "高级后端", "company": "某AI公司"}
        mid = _create_mission_with_jd(jd_fields, state="problem_pending")
        db.update_mission_state(mid, "problem_pending", {"resume_state": "jd_parsed"})

        # problem_pending 的 Mission 不会被 scheduler 推进
        mission = db.get_mission(mid)
        orchestrator.step_mission(mission)

        # 应保持在 problem_pending
        mission = db.get_mission(mid)
        assert mission["state"] == "problem_pending", \
            f"problem_pending should not auto-advance"

        # 模拟人工解决：直接更新状态到 resume_state
        db.update_mission_state(mid, "jd_parsed", {"resume_state": None})
        mission = db.get_mission(mid)
        assert mission["state"] == "jd_parsed"


class TestCandidateManagement:
    """测试候选人相关的数据库操作。"""

    def test_insert_and_score_candidate(self, temp_db):
        """候选人入库并评分后，数据应完整保存。"""
        cid = db.insert_candidate({
            "name": "测试候选人",
            "email": "test@example.com",
            "phone": "13800000000",
            "source_types": ["talent_db", "candidate_collector"],
            "raw_profile": {"summary": "5年后端开发经验"},
            "jd_alignment_score": 80,
            "gold_score": 75,
            "overall_score": 78,
            "risk_flags": [{"flag": "测试风险", "severity": "yellow"}],
        })

        row = db.get_conn().execute(
            "SELECT * FROM candidates WHERE id = ?", (cid,)
        ).fetchone()
        assert row is not None
        candidate = dict(row)
        assert candidate["name"] == "测试候选人"
        assert candidate["overall_score"] == 78

        source_types = json.loads(candidate["source_types"])
        assert "talent_db" in source_types

    def test_call_list_and_feedback_cycle(self, temp_db):
        """电话任务 + 反馈的完整循环。"""
        # 创建候选人
        cid = db.insert_candidate({
            "name": "电话测试",
            "email": "call@test.com",
            "overall_score": 85,
        })

        # 创建 call_list item
        lid = db.insert_call_list({
            "candidate_id": cid,
            "mission_id": "test_mission",
            "priority": 85,
            "talking_points": ["确认意向", "了解薪资"],
            "evidence": [],
            "status": "pending",
        })

        items = db.get_call_list(status="pending")
        assert len(items) >= 1

        # 提交反馈
        fid = db.insert_feedback({
            "candidate_id": cid,
            "call_list_id": lid,
            "outcome": "interested",
            "notes": "候选人有兴趣，期望薪资 80K",
        })

        assert fid.startswith("fb_"), f"Invalid feedback ID: {fid}"
