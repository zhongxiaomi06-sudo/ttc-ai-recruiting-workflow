"""JD 解析 Agent：把原始 JD 文本变成结构化字段。"""
import logging
from typing import Dict, Any

from .. import db
from ..core.jd_parser import extract_jd

logger = logging.getLogger(__name__)


def parse(mission: Dict[str, Any], jd_record: Dict[str, Any]) -> Dict[str, Any]:
    """解析 JD，记录 Agent 运行日志。"""
    jd_fields = extract_jd(jd_record.get("raw_text", ""))
    logger.info("Mission %s JD parsed: %s", mission["id"], jd_fields.get("position"))
    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="jd_agent.parse",
        input_data={"jd_record_id": jd_record.get("id"), "title": jd_record.get("title")},
        output_data=jd_fields,
        decision="jd_parsed",
    )
    return jd_fields
