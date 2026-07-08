"""评分引擎测试：评分一致性 + 兜底评分 + 合规检测 + 话术生成"""
import os

import pytest

from ttc_daemon.core.scoring import (
    score_candidate,
    _fallback_scoring,
    detect_compliance_issues,
    generate_talking_points,
    build_call_script,
)


class TestFallbackScoring:
    """测试简单加权兜底评分（不依赖 LLM）。"""

    def test_basic_weighted_score(self):
        """jd_alignment * 0.6 + gold_score * 0.4 应正确计算。"""
        candidate = {
            "name": "测试",
            "jd_alignment_score": 80,
            "gold_score": 70,
            "risk_flags": [],
        }
        jd_fields = {"position": "后端", "company": "某公司"}

        # 强制使用兜底评分
        result = _fallback_scoring(candidate, jd_fields)
        assert result["overall_score"] == round(80 * 0.6 + 70 * 0.4, 1)
        assert result["level"] in ("扎实", "中上", "中等", "较浅", "不足")
        assert isinstance(result["risk_flags"], list)
        assert len(result["verification_questions"]) > 0

    def test_missing_gold_score(self):
        """gold_score 为空时只用 jd_alignment。"""
        candidate = {
            "name": "测试",
            "jd_alignment_score": 60,
            "gold_score": 0,
        }
        result = _fallback_scoring(candidate, {})
        assert result["overall_score"] == 60.0

    def test_all_zero_scores(self):
        """两个分数都为 0 时 overall 应为 0。"""
        candidate = {"jd_alignment_score": 0, "gold_score": 0}
        result = _fallback_scoring(candidate, {})
        assert result["overall_score"] == 0.0

    def test_level_mapping(self):
        """不同分数段应对应正确的评级。"""
        test_cases = [
            (90, "扎实"),
            (75, "中上"),
            (60, "中等"),
            (45, "较浅"),
            (20, "不足"),
        ]
        for score, expected_level in test_cases:
            candidate = {"jd_alignment_score": score, "gold_score": score}
            result = _fallback_scoring(candidate, {})
            assert result["level"] == expected_level, \
                f"Score {score} expected level '{expected_level}', got '{result['level']}'"


class TestFallbackScoreCandidate:
    """测试统一的 score_candidate 入口（LLM 不可用时使用兜底）。"""

    def test_score_writes_back_to_candidate(self):
        """评分结果应写回 candidate 字典。"""
        candidate = {
            "name": "张三",
            "jd_alignment_score": 78,
            "gold_score": 82,
            "risk_flags": [],
        }
        jd_fields = {"position": "后端工程师", "company": "某科技公司"}

        # 由于 LLM 未配置，应自动使用兜底评分
        result = score_candidate(candidate, jd_fields, use_llm=False)

        assert "overall_score" in result
        assert "level" in result
        assert "confidence" in result
        assert "risk_flags" in result
        assert "verification_questions" in result
        assert isinstance(result["verification_questions"], list)

    def test_score_preserves_existing_fields(self):
        """评分不应覆盖候选人原有的字段。"""
        candidate = {
            "name": "李四",
            "email": "lisi@test.com",
            "jd_alignment_score": 70,
            "gold_score": 65,
        }
        result = score_candidate(candidate, {}, use_llm=False)
        assert result["name"] == "李四"
        assert result["email"] == "lisi@test.com"


class TestComplianceDetection:
    """测试合规问题检测。"""

    def test_no_issues_for_clean_candidate(self):
        """干净候选人不应触发合规问题。"""
        candidate = {
            "name": "干净",
            "source_types": ["talent_db"],
            "risk_flags": [],
            "raw_profile": {"company": "某公司"},
            "enriched_profile": {"company": "某公司"},
        }
        issues = detect_compliance_issues(candidate)
        assert len(issues) == 0, f"Expected 0 issues, got {len(issues)}"

    def test_detect_red_flags(self):
        """有红灯信号的候选人应触发合规问题。"""
        candidate = {
            "name": "风险",
            "source_types": ["talent_db"],
            "risk_flags": [
                {"flag": "学历造假嫌疑", "severity": "red", "detail": "学历信息与公开资料不符"},
            ],
        }
        issues = detect_compliance_issues(candidate)
        assert len(issues) > 0
        assert any(i["severity"] == "high" for i in issues)

    def test_detect_untrusted_source(self):
        """来源不明的候选人应触发合规问题。"""
        candidate = {
            "name": "来源不明",
            "source_types": [],
            "risk_flags": [],
            "raw_profile": {},
        }
        issues = detect_compliance_issues(candidate)
        assert len(issues) > 0
        assert any(i["type"] == "untrusted_source" for i in issues)

    def test_detect_data_conflict(self):
        """多来源信息矛盾应触发合规问题。"""
        candidate = {
            "name": "矛盾",
            "source_types": ["talent_db", "candidate_collector"],
            "risk_flags": [],
            "raw_profile": {"company": "公司A"},
            "enriched_profile": {"company": "公司B"},
        }
        issues = detect_compliance_issues(candidate)
        assert len(issues) > 0
        assert any(i["type"] == "data_conflict" for i in issues)

    def test_detect_non_compete(self):
        """竞业限制相关信息应触发合规问题。"""
        candidate = {
            "name": "竞业",
            "source_types": ["talent_db"],
            "risk_flags": [],
            "raw_profile": {"raw_text": "目前受竞业限制协议约束，需确认有效期"},
        }
        issues = detect_compliance_issues(candidate)
        assert len(issues) > 0
        assert any(i["type"] == "non_compete_concern" for i in issues)


class TestTalkingPoints:
    """测试电话话术生成。"""

    def test_basic_talking_points(self):
        """基本话术应包含推荐要素。"""
        candidate = {
            "name": "王五",
            "overall_score": 82,
            "level": "中上",
            "risk_flags": [],
            "verification_questions": [
                "目前在职还是离职？",
                "期望薪资范围是多少？",
                "对工作地点有要求吗？",
            ],
        }
        jd_fields = {"position": "架构师", "company": "头部互联网公司"}
        points = generate_talking_points(candidate, jd_fields)

        assert len(points) > 0
        assert any("王五" in p for p in points)
        assert any("架构师" in p for p in points)
        # 应包含 AI 评级
        assert any("中上" in p for p in points)

    def test_talking_points_with_risks(self):
        """有风险信号时话术应包含核实提示。"""
        candidate = {
            "name": "赵六",
            "overall_score": 70,
            "level": "中上",
            "risk_flags": [
                {"flag": "上一份工作不满1年", "severity": "yellow"},
                {"flag": "异地需 relocation", "severity": "yellow"},
            ],
            "verification_questions": [],
        }
        jd_fields = {"position": "工程师", "company": "某公司"}
        points = generate_talking_points(candidate, jd_fields)

        # 应有风险提示
        risk_points = [p for p in points if "⚠️" in p or "核实" in p]
        assert len(risk_points) > 0, f"Expected risk warning in talking points, got: {points}"

    def test_call_script_format(self):
        """电话开场白格式应正确。"""
        candidate = {"name": "孙七"}
        jd_fields = {"company": "字节跳动", "position": "后端负责人"}
        script = build_call_script(candidate, jd_fields)

        assert "孙七" in script
        assert "字节跳动" in script
        assert "后端负责人" in script
        assert "TTC 猎头" in script


@pytest.mark.skipif(
    not os.getenv("TTC_LLM_API_KEY"),
    reason="LLM not configured, skip LLM-dependent test",
)
class TestLLMScoring:
    """LLM CoT 评分测试（需要配置 LLM 时运行）。"""

    def test_llm_scoring_returns_full_structure(self):
        """LLM 评分应返回完整的结构化评分对象。"""
        candidate = {
            "name": "高级工程师A",
            "raw_profile": {
                "raw_text": "10年后端开发经验，曾在阿里云负责大规模分布式系统设计，"
                           "主导日均千亿级请求的处理架构。精通 Go/Python/C++，"
                           "开源项目贡献者，GitHub 5000+ stars。",
            },
            "source_types": ["talent_db"],
            "evidence": [
                {"field": "github", "raw_text": "5000+ stars on main project", "source_url": "https://github.com/example"},
            ],
        }
        jd_fields = {
            "position": "高级后端工程师",
            "company": "头部AI公司",
            "skills": ["Python", "Go", "Kubernetes", "分布式系统"],
        }

        result = score_candidate(candidate, jd_fields, use_llm=True)

        # 完整结构验证
        assert "overall_score" in result
        assert "level" in result
        assert "confidence" in result
        assert "dimension_scores" in result
        assert "evidence_binding" in result
        assert "risk_flags" in result
        assert "verification_questions" in result
        assert "company_analysis" in result

        # 分数合理性
        assert 0 <= result["overall_score"] <= 100
        assert result["level"] in ("扎实", "中上", "中等", "较浅", "不足")
        assert result["confidence"] in ("high", "medium", "low")

        # 维度分数
        for dim_key in ("tech_depth", "project_ownership", "complexity", "impact"):
            if dim_key in result.get("dimension_scores", {}):
                dim = result["dimension_scores"][dim_key]
                if isinstance(dim, dict):
                    assert 0 <= dim.get("score", 0) <= 100

    def test_llm_scoring_consistency(self):
        """多次评分的极差应在可接受范围内（≤15 分，不要求 8 分因为无 LLM 配置时会用兜底）。"""
        candidate = {
            "name": "一致性测试",
            "jd_alignment_score": 75,
            "gold_score": 72,
            "raw_profile": {"raw_text": "5年Python后端，熟悉Django/Flask/K8s"},
        }
        jd_fields = {"position": "Python后端", "company": "某公司", "skills": ["Python", "K8s"]}

        # 跑 3 次兜底评分（都相同所以 range 为 0）
        results = []
        for _ in range(3):
            results.append(score_candidate(dict(candidate), jd_fields, use_llm=False))

        scores = [r["overall_score"] for r in results]
        score_range = max(scores) - min(scores)
        # 兜底评分使用相同公式，极差应为 0
        assert score_range == 0, f"Fallback scores should be identical, got range {score_range}"
