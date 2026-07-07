import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


SAMPLE = """
张某 31岁 北京 8年工作经验
复旦大学 本科
罗兰贝格 咨询顾问，负责消费行业品牌定位项目，向客户CEO汇报。
百事 战略经理，主导新品上市、产品创新、GTM和渠道策略。
"""


class ParserTests(unittest.TestCase):
    def test_qiming_profile(self):
        result = app.parse_candidate(app.CapturePayload(title="张某-在线简历", heading="张某", text=SAMPLE, url="https://www.zhipin.com/candidate/1"))
        self.assertEqual(result["name"], "张某")
        self.assertEqual(result["platform"], "BOSS直聘")
        self.assertEqual(result["undergraduate_tier"], "985")
        self.assertGreaterEqual(result["score"], 85)
        self.assertTrue(result["consulting_evidence"])
        self.assertTrue(result["inhouse_evidence"])

    def test_clean_text_deduplicates_lines(self):
        self.assertEqual(app.clean_text(" A  \nA\n\n B "), "A\nB")

    def test_name_from_prefixed_filename(self):
        text = "\n能力简介\n工作经历\nWenda Yin 殷闻达\n北京\n"
        self.assertEqual(app.infer_name("【消费品牌策略顾问】_北京 25K-殷闻达 5年.pdf", "", text), "殷闻达")

    def test_chinese_name_precedes_english_filename(self):
        self.assertEqual(app.infer_name("Guofu(Rachel) RAO_CV.pdf", "", "饶帼馥\n联系电话\n"), "饶帼馥")

    def test_job_prefixed_filename_beats_page_button(self):
        title = "【新消费品牌策略_北京 50-55K】李潭清 8年.pdf"
        text = "后一个月\n设置\n工作经历\n"
        self.assertEqual(app.infer_name(title, "", text), "李潭清")

    def test_boss_native_profile(self):
        text = """詹先生
31岁
本科
9年
在职-考虑机会
北京
战略咨询
30-50K
工作经历
美团
业务策略
2025.11 - 至今
负责业务战略规划、产品创新和渠道策略，向管理层汇报。
帕特侬战略咨询
高级战略顾问
2021.11 - 2022.05
参与消费行业战略咨询项目。
教育经历
中南财经政法大学
会计学
本科
2013 - 2017
211院校"""
        result = app.parse_candidate(app.CapturePayload(
            title="BOSS直聘", heading="詹先生", text=text,
            url="https://www.zhipin.com/web/geek/detail/example"
        ))
        self.assertEqual(result["name"], "詹先生")
        self.assertEqual(result["explicit_age"], 31)
        self.assertEqual(result["experience_years"], 9)
        self.assertEqual(result["current_company"], "美团")
        self.assertEqual(result["current_role"], "业务策略")
        self.assertEqual(result["expected_salary"], "30-50K")
        self.assertEqual(result["undergraduate_tier"], "211")
        self.assertEqual(len(result["experiences"]), 2)
        self.assertGreaterEqual(result["score"], 85)

    def test_age_over_33_is_zero(self):
        text = SAMPLE.replace("31岁", "34岁")
        result = app.parse_candidate(app.CapturePayload(
            title="候选人", heading="张某", text=text
        ))
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["hard_filter_reason"], "年龄超过33岁")
        self.assertEqual(result["recommendation"], "不符合年龄硬性要求")


if __name__ == "__main__":
    unittest.main()
