"""仓位管理：Recruiting Quant OS 仓位状态机。

将顾问时间类比为资金，Mission 类比为标的，推荐类比为建仓，反馈类比为市场信号。

仓位状态机：
  DISCOVERED → TRIAL（小仓，推1-3人）
    → ACTIVE（标准，3-5人）→ SCALE_UP（重仓）
    → SCALE_DOWN → STOP
  DISCOVERED → WATCHING（评分<40，不投入）

触发信号：
- 电话反馈 interested → 加分，可能 SCALE_UP
- 电话反馈 not_interested → 减分，可能 SCALE_DOWN
- 长期无响应 → 降级或 STOP
- 客户反馈快 → 加分
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .. import db

logger = logging.getLogger(__name__)


def _parse_candidate_ids(mission: Dict[str, Any]) -> list:
    """Safely parse candidate_ids from a mission record (JSON string or list)."""
    raw = mission.get("candidate_ids")
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []

# 仓位状态定义
ALLOCATION_STATES = {
    "DISCOVERED": {
        "label": "已发现",
        "level": 0,
        "description": "新 JD 入库，尚未决策是否投入",
        "max_candidates": 0,
    },
    "WATCHING": {
        "label": "观察中",
        "level": 0,
        "description": "评分<40，暂不投入顾问时间",
        "max_candidates": 0,
    },
    "TRIAL": {
        "label": "小仓试水",
        "level": 1,
        "description": "推送 1-3 位候选人，测试客户反馈速度",
        "max_candidates": 3,
    },
    "ACTIVE": {
        "label": "标准仓位",
        "level": 2,
        "description": "推送 3-5 位候选人，正常投入",
        "max_candidates": 5,
    },
    "SCALE_UP": {
        "label": "重仓",
        "level": 3,
        "description": "客户反馈好，加大人力投入",
        "max_candidates": 10,
    },
    "SCALE_DOWN": {
        "label": "减仓",
        "level": 1,
        "description": "反馈不佳或人才供给不足，减少投入",
        "max_candidates": 2,
    },
    "STOP": {
        "label": "停止",
        "level": -1,
        "description": "客户不再需要或完全无合适人选",
        "max_candidates": 0,
    },
}

# 状态转移规则
TRANSITIONS = {
    "DISCOVERED": ["TRIAL", "WATCHING", "STOP"],
    "WATCHING": ["TRIAL", "DISCOVERED", "STOP"],
    "TRIAL": ["ACTIVE", "SCALE_DOWN", "WATCHING", "STOP"],
    "ACTIVE": ["SCALE_UP", "SCALE_DOWN", "TRIAL", "STOP"],
    "SCALE_UP": ["ACTIVE", "SCALE_DOWN", "TRIAL", "STOP"],
    "SCALE_DOWN": ["TRIAL", "ACTIVE", "WATCHING", "STOP"],
    "STOP": ["DISCOVERED", "WATCHING"],  # 可重新激活
}

# 每次回调反馈的分数调整
FEEDBACK_SCORE_DELTA = {
    "interested": +15,
    "not_interested": -8,
    "no_answer": -3,
    "wrong_info": -10,
}


def get_allocation_state(mission: Dict[str, Any]) -> str:
    """获取 Mission 当前的仓位状态。"""
    return mission.get("allocation_state") or "DISCOVERED"


def compute_priority_score(mission: Dict[str, Any]) -> float:
    """计算 Mission 的优先级评分（0-100）。

    评分因素：
    - 仓位等级（SCALE_UP > ACTIVE > TRIAL > 其他）
    - 创建时间（新 Mission 优先）
    - 是否有待完成的 human_tasks（有则不降级）
    - 是否有关键反馈
    """
    allocation = get_allocation_state(mission)
    level = ALLOCATION_STATES.get(allocation, {}).get("level", 0)

    # 基础分：仓位等级 × 20
    base = level * 20

    # 新 Mission 加分（24 小时内 +10）
    created_at = mission.get("created_at", "")
    try:
        from datetime import datetime, timedelta, timezone
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age_hours < 24:
            base += 10
        elif age_hours < 72:
            base += 5
    except (ValueError, TypeError):
        pass

    # 有活跃 human_tasks 的不降分
    tasks = db.get_mission_human_tasks(mission["id"])
    active_tasks = [t for t in tasks if t["status"] in ("pending", "notified", "opened")]
    if active_tasks:
        base += 5

    # 长期无进展降分（updated_at 超过 7 天）
    updated_at = mission.get("updated_at", "")
    try:
        from datetime import datetime, timedelta, timezone
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        days_stale = (datetime.now(timezone.utc) - updated).total_seconds() / 86400
        if days_stale > 14:
            base -= 30
        elif days_stale > 7:
            base -= 15
    except (ValueError, TypeError):
        pass

    return max(0.0, min(100.0, base))


def evaluate_allocation(mission: Dict[str, Any]) -> Tuple[str, str]:
    """根据 Mission 的反馈数据评估仓位调整。

    Returns:
        (new_state, reason) — 新的仓位状态和调整原因
    """
    current = get_allocation_state(mission)
    mid = mission["id"]

    # 收集反馈信号
    tasks = db.get_mission_human_tasks(mid)
    call_tasks = [t for t in tasks if t.get("task_type") == "call" and t.get("status") == "completed"]

    if not call_tasks:
        # 无反馈数据 → 保持或初始分配
        candidates_count = len(_parse_candidate_ids(mission))
        if current == "DISCOVERED":
            if candidates_count >= 3:
                return ("TRIAL", "有 ≥3 位候选人，自动进入小仓试水")
            return (current, "等待候选人积累")
        return (current, "无反馈数据，保持当前仓位")

    # 计算信号总分
    total_signal = 0
    outcomes = {}
    for t in call_tasks:
        result = t.get("result", "") or "{}"
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {}
        outcome = result.get("outcome", "")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        delta = FEEDBACK_SCORE_DELTA.get(outcome, 0)
        total_signal += delta

    total_calls = len(call_tasks)
    interest_rate = outcomes.get("interested", 0) / max(total_calls, 1)

    # 调整逻辑
    if total_signal >= 20 and interest_rate >= 0.5:
        if current == "TRIAL":
            return ("ACTIVE", f"信号积极（interest_rate={interest_rate:.0%}），升级到标准仓位")
        if current in ("ACTIVE", "SCALE_UP"):
            return ("SCALE_UP", f"信号持续积极（interest_rate={interest_rate:.0%}），加仓")
        return (current, f"信号积极，建议升级仓位")

    if total_signal <= -15:
        if current in ("SCALE_UP", "ACTIVE"):
            return ("SCALE_DOWN", f"信号恶化（总分={total_signal}），减仓")
        if current == "TRIAL":
            return ("WATCHING", f"试水结果不佳（总分={total_signal}），转为观察")
        return (current, f"信号恶化，建议降级")

    if total_calls >= 3 and interest_rate == 0:
        if current not in ("WATCHING", "STOP"):
            return ("WATCHING", "连续无兴趣反馈，转为观察")

    return (current, "信号中性，维持当前仓位")


def update_allocation(mission_id: str) -> Tuple[str, str]:
    """更新 Mission 的仓位状态。

    Returns:
        (new_state, reason)
    """
    mission = db.get_mission(mission_id)
    if not mission:
        return ("DISCOVERED", "Mission not found")

    new_state, reason = evaluate_allocation(mission)
    old_state = get_allocation_state(mission)

    if new_state != old_state:
        priority = compute_priority_score(mission)
        db.update_mission_state(
            mission_id,
            mission["state"],
            {
                "allocation_state": new_state,
                "priority_score": priority,
            },
        )
        logger.info(
            "Mission %s allocation: %s → %s (reason: %s)",
            mission_id, old_state, new_state, reason,
        )

        db.insert_agent_run(
            mission_id=mission_id,
            agent_name="position_allocator.update_allocation",
            input_data={"old_state": old_state, "feedbacks": "from evaluate"},
            output_data={"new_state": new_state, "reason": reason},
            decision=f"allocation_{old_state}_to_{new_state}",
        )
    else:
        # 即使仓位不变，也更新优先级
        priority = compute_priority_score(mission)
        db.update_mission_state(
            mission_id, mission["state"], {"priority_score": priority},
        )

    return new_state, reason


def init_mission_allocation(mission: Dict[str, Any]) -> str:
    """新 Mission 初始化仓位状态。

    Returns:
        allocation_state
    """
    candidates_count = len(_parse_candidate_ids(mission))

    if candidates_count >= 3:
        state = "TRIAL"
    else:
        state = "DISCOVERED"

    priority = compute_priority_score(mission)
    db.update_mission_state(
        mission["id"],
        mission.get("state", "created"),
        {"allocation_state": state, "priority_score": priority},
    )

    logger.info("Mission %s initialized with allocation %s (priority=%.1f)", mission["id"], state, priority)
    return state
