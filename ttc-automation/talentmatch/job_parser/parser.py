"""Job description parser"""
from __future__ import annotations
import json
import os
from typing import Optional
from loguru import logger
from .models import JobRequirements
from resume_parser.llm_utils import get_llm, reset_llm

JD_EXTRACTION_PROMPT = """你是资深猎头JD分析师。从岗位需求文本提取结构化信息。

规则：
1. required_skills 和 preferred_skills 要区分清楚
2. hidden_requirements 提取JD中没明说但实际很重要的要求
3. key_selling_points 提取可以用来吸引候选人的卖点
4. urgency 根据语言紧迫程度判断
5. priority_level: P0=紧急核心岗/P1=重要岗/P2=普通岗

返回JSON：
{"title":"","company":"","department":"","location":"","employment_type":"","description":"","required_skills":[],"preferred_skills":[],"min_years_experience":0,"max_years_experience":null,"education":"","salary_range":"","company_tier":"","industry":"","urgency":"","team_size":null,"report_to":"","key_selling_points":[],"hidden_requirements":[],"priority_level":""}"""


class JobParser:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def parse(self, jd_text: str, source: str = "") -> JobRequirements:
        logger.info(f"Parsing JD from {source or 'text'}")
        structured = self._llm_extract(jd_text)
        structured["raw_text"] = jd_text[:2000]
        structured["source"] = source
        try:
            return JobRequirements(**structured)
        except Exception as e:
            logger.error(f"JD Pydantic validation failed: {e}")
            return JobRequirements(raw_text=jd_text[:2000], source=source,
                                  description=f"JD解析部分失败: {str(e)[:100]}")

    def _llm_extract(self, text: str) -> dict:
        client, model = get_llm()
        if not client:
            return {}
        try:
            resp = client.chat.completions.create(
                model=model or self.model,
                messages=[
                    {"role": "system", "content": JD_EXTRACTION_PROMPT},
                    {"role": "user", "content": f"分析岗位需求：\n\n{text[:8000]}"}
                ],
                temperature=0.1, max_tokens=3000,
                response_format={"type": "json_object"}
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.error(f"JD LLM extraction failed: {e}")
            reset_llm()
            return {}
