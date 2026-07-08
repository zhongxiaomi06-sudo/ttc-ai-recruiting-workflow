"""行业分类器 — 基于规则+LLM推理候选人行业标签

粒度从粗到细:
  大类: 互联网/金融/医疗/教育/制造业/企业服务/游戏/硬件…
  细类: 互联网·电商/SaaS/社交/金融科技…

自动在 save_candidate 时调用。
"""
from __future__ import annotations
import json
import re
from typing import List, Optional

# ── 规则引擎：关键词→行业映射 ──

INDUSTRY_RULES: List[tuple] = [
    # (关键词, 大类, 细类)
    (r"推荐系统|搜广推|广告系统|搜索算法|NLP|计算机视觉|大模型|LLM|AIGC|深度学习|机器学习", "互联网/AI", "AI·算法"),
    (r"电商|交易平台|供应链|O2O|新零售|跨境电商", "互联网", "互联网·电商"),
    (r"SaaS|PaaS|云服务|企业服务|ERP|CRM|飞书|钉钉", "企业服务", "企业服务·SaaS"),
    (r"社交|社区|内容平台|短视频|直播|小红书|抖音", "互联网", "互联网·社交/内容"),
    (r"金融|银行|证券|保险|支付|量化|风控|信贷", "金融", "金融·科技"),
    (r"教育|在线教育|培训|学习平台|EdTech", "教育", "教育·在线教育"),
    (r"医疗|医药|健康|生物|基因|医院|医疗器械", "医疗健康", "医疗·科技"),
    (r"游戏|手游|端游|Unity|Unreal|游戏开发|休闲游戏", "游戏", "游戏·开发"),
    (r"硬件|芯片|半导体|嵌入式|IoT|机器人|自动驾驶", "硬件/半导体", "硬件·研发"),
    (r"制造|工业|工厂|供应链|物流", "制造业", "制造业·供应链"),
    (r"房地产|建筑|物业|家装", "房地产", "房地产·运营"),
    (r"咨询|投行|VC|PE|投资|券商", "金融", "金融·投资"),
    (r"法律|律师|知产|合规", "专业服务", "专业服务·法律"),
    (r"人力资源|猎头|招聘|HR|人力", "专业服务", "专业服务·人力资源"),
    (r"传媒|广告|公关|营销|市场|品牌", "传媒/广告", "传媒·营销"),
    (r"新能源|碳中和|光伏|风电|储能|电池", "新能源", "新能源·研发"),
    (r"电信|通信|5G|运营商|移动|联通|电信", "通信", "通信·技术"),
    (r"政府|国企|央企|事业单位|机关", "政府/公共事业", "政府·信息化"),
    (r"区块链|Web3|NFT|DeFi|数字货币", "区块链/Web3", "区块链·开发"),
    (r"大数据|数据平台|数据工程|数据仓库|ETL|BI", "互联网", "互联网·数据平台"),
    (r"运维|DevOps|SRE|基础设施|K8s|Docker|云原生", "企业服务", "企业服务·云原生"),
    (r"前端|后端|全栈|架构师|技术经理|技术总监|CTO", "互联网", "互联网·技术研发"),
    (r"产品经理|产品总监|产品负责人|产品运营", "互联网", "互联网·产品"),
]

# ── 公司→行业映射 ──

COMPANY_INDUSTRY: dict = {
    "阿里巴巴|淘宝|天猫|菜鸟|饿了么": ("互联网", "互联网·电商"),
    "腾讯|微信": ("互联网", "互联网·社交/内容"),
    "字节跳动|抖音|今日头条|飞书": ("互联网", "互联网·内容/SaaS"),
    "百度|百度云": ("互联网/AI", "AI·搜索/自动驾驶"),
    "美团|大众点评": ("互联网", "互联网·本地生活"),
    "京东|京东云": ("互联网", "互联网·电商"),
    "拼多多|temu": ("互联网", "互联网·电商"),
    "快手": ("互联网", "互联网·社交/内容"),
    "小红书": ("互联网", "互联网·社交/内容"),
    "蚂蚁集团|支付宝|网商银行": ("金融", "金融·科技"),
    "华为|荣耀": ("硬件/半导体", "硬件·通信/终端"),
    "比亚迪|蔚来|小鹏|理想": ("制造业", "制造业·新能源车"),
    "微软|Google|Meta|Amazon|Apple": ("互联网", "互联网·国际化"),
    "大疆": ("硬件/半导体", "硬件·无人机/机器人"),
}


def classify_industry(
    current_company: str = "",
    current_role: str = "",
    skills: Optional[List[str]] = None,
    summary: str = "",
) -> List[str]:
    """基于候选人信息推理行业标签，返回 ['大类·细类'] 列表"""
    skills = skills or []
    text = f"{current_role} {summary} {' '.join(skills)}".lower()
    company_text = (current_company or "").lower()
    
    result = []
    
    # 1. 公司匹配（优先级最高）
    for pattern, (big, sub) in COMPANY_INDUSTRY.items():
        if re.search(pattern.lower(), company_text):
            result.append(f"{big}·{sub.split('·')[-1]}")
            break
    
    # 2. 角色/技能关键词匹配
    for pattern, big, sub in INDUSTRY_RULES:
        if re.search(pattern.lower(), text):
            tag = f"{big}·{sub.split('·')[-1]}"
            if tag not in result:
                result.append(tag)
    
    # 3. 兜底：纯技术角色
    if not result:
        role = (current_role or "").lower()
        if any(kw in role for kw in ["工程师", "开发", "程序员", "技术", "工程"]):
            result.append("互联网·技术研发")
        elif any(kw in role for kw in ["产品", "运营", "设计", "市场"]):
            result.append("互联网·产品/运营")
        elif current_company and current_company.strip():
            result.append("企业服务·其他")
        else:
            result.append("未分类")
    
    return result


def enrich_with_llm(
    current_company: str = "",
    current_role: str = "",
    skills: Optional[List[str]] = None,
    summary: str = "",
    current_tags: Optional[List[str]] = None,
) -> List[str]:
    """用规则引擎推理，不需要 LLM 调用（当前阶段规则够用）"""
    classified = classify_industry(current_company, current_role, skills, summary)
    
    # 如果已有 tags，合并去重
    existing = current_tags or []
    all_tags = list(dict.fromkeys(existing + classified))  # 有序去重
    
    return all_tags if all_tags else ["未分类"]


def batch_enrich(candidates: List[dict]) -> List[dict]:
    """批量填充 industry_tags（不需要 LLM，纯规则）"""
    updated = []
    for c in candidates:
        skills_raw = c.get("skills", "[]")
        if isinstance(skills_raw, str):
            try:
                skills = json.loads(skills_raw) if skills_raw.startswith("[") else []
            except (json.JSONDecodeError, TypeError):
                skills = []
        else:
            skills = skills_raw or []
        
        current_tags_raw = c.get("industry_tags", "[]")
        if isinstance(current_tags_raw, str):
            try:
                current_tags = json.loads(current_tags_raw) if current_tags_raw.startswith("[") else []
            except (json.JSONDecodeError, TypeError):
                current_tags = []
        else:
            current_tags = current_tags_raw or []
        
        new_tags = enrich_with_llm(
            current_company=c.get("current_company", ""),
            current_role=c.get("current_role", ""),
            skills=skills,
            summary=c.get("summary", ""),
            current_tags=current_tags,
        )
        
        if new_tags != current_tags:
            c["industry_tags"] = json.dumps(new_tags, ensure_ascii=False)
            updated.append(c)
    
    return updated
