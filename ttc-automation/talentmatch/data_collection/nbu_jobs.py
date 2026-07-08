"""
宁波大学就业网 - 校招岗位采集器
从宁大就业网扒所有来校招聘的岗位信息，填充TalentMatch的JD库
不需要登录，公开数据
"""

import requests
import re
import json
import time
from urllib.parse import urlencode
from datetime import datetime

class NBUJobCollector:
    """宁大校招岗位采集"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://ndjy.nbu.edu.cn/',
        })
        self.base = 'https://ndjy.nbu.edu.cn'
    
    def search_jobs(self, keyword='', page=1, page_size=20, 
                    salary_min=0, salary_max=0, 
                    degree='', company_type='', company_size=''):
        """搜索岗位"""
        # 构建筛选路径
        path = '/job/search'
        params = {
            'key': keyword,
            'page': page,
        }
        
        resp = self.session.post(f"{self.base}{path}", data=params, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ 搜索失败: {resp.status_code}")
            return []
        
        # 从HTML里提取岗位列表
        jobs = self._parse_job_list(resp.text)
        return jobs
    
    def _parse_job_list(self, html):
        """解析岗位列表HTML"""
        jobs = []
        
        # 找到岗位列表区域
        # 才立方系统的岗位卡片结构
        items = re.findall(
            r'<div[^>]*class="[^"]*job-item[^"]*"[^>]*>'
            r'([\s\S]*?)</div>\s*</div>\s*</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )
        
        if not items:
            # 尝试另一种结构
            items = re.findall(
                r'<li[^>]*class="[^"]*job[^"]*"[^>]*>([\s\S]*?)</li>',
                html, re.DOTALL
            )
        
        if not items:
            # 直接找所有岗位数据块
            blocks = re.findall(r'<div[^>]*class="[^"]*list-item[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>', html, re.DOTALL)
            if not blocks:
                blocks = re.findall(r'<div[^>]*class="[^"]*(?:job|position|recruit)[^"]*"[^>]*>([\s\S]*?)</div>', html, re.DOTALL)
            items = blocks
        
        for item in items:
            job = self._parse_single_job(item)
            if job:
                jobs.append(job)
        
        return jobs
    
    def _parse_single_job(self, html):
        """从单个岗位HTML提取信息"""
        job = {}
        
        # 标题
        m = re.search(r'<a[^>]*>([^<]+)</a>', html)
        if m:
            title = m.group(1).strip()
            if title:
                job['title'] = title
        
        # 链接
        m = re.search(r'<a[^>]*href="(/job/detail/[^"]+)"', html)
        if m:
            job['url'] = self.base + m.group(1)
        
        # 公司名
        m = re.search(r'公司[：:]\s*([^<\n]+)', html)
        if m:
            job['company'] = m.group(1).strip()
        
        # 薪资
        m = re.search(r'(?:薪资|工资|待遇)[：:]\s*([^<\n]+)', html)
        if m:
            job['salary'] = m.group(1).strip()
        
        # 学历
        m = re.search(r'学历[：:]\s*([^<\n]+)', html)
        if m:
            job['degree'] = m.group(1).strip()
        
        # 地点
        m = re.search(r'(?:地点|地区|城市)[：:]\s*([^<\n]+)', html)
        if m:
            job['location'] = m.group(1).strip()
        
        # 发布时间
        m = re.search(r'(?:发布|时间)[：:]\s*([^<\n]+)', html)
        if m:
            job['publish_time'] = m.group(1).strip()
        
        # 直接把所有文本提取出来
        text = re.sub(r'<[^>]+>', ' ', html).strip()
        text = re.sub(r'\s+', ' ', text)
        if text and not job.get('title'):
            # 尝试从纯文本中提取标题
            parts = text.split()
            if parts:
                job['title'] = parts[0]
        
        return job if job.get('title') else None
    
    def get_job_detail(self, url):
        """获取岗位详情页"""
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        html = resp.text
        detail = {}
        
        # 提取详情内容
        content_match = re.search(
            r'<div[^>]*class="[^"]*(?:content|detail|article)[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>',
            html, re.DOTALL
        )
        
        if content_match:
            content = content_match.group(1)
            text = re.sub(r'<[^>]+>', '\n', content)
            text = re.sub(r'\s+', ' ', text).strip()
            detail['description'] = text
        
        # 提取公司信息
        company_match = re.search(
            r'公司[：:]\s*([^<\n]+)',
            html
        )
        if company_match:
            detail['company'] = company_match.group(1).strip()
        
        return detail
    
    def collect_all(self, keywords=None, max_pages=50):
        """
        采集所有校招岗位
        keywords: 搜索关键词列表，None则搜索全部
        """
        if keywords is None:
            keywords = ['', '实习', '校招', '应届']
        
        all_jobs = []
        
        for kw in keywords:
            print(f"\n🔍 搜索: '{kw}'")
            for page in range(1, max_pages + 1):
                jobs = self.search_jobs(keyword=kw, page=page)
                if not jobs:
                    break
                
                all_jobs.extend(jobs)
                print(f"  第{page}页: {len(jobs)}个岗位 (累计{len(all_jobs)})")
                time.sleep(0.5)
        
        # 去重
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            key = f"{job.get('title')}|{job.get('company')}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        # 保存
        filename = f"nbu_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output = {
            'total': len(unique_jobs),
            'source': '宁波大学就业信息网',
            'timestamp': datetime.now().isoformat(),
            'jobs': unique_jobs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 采集完成！共{len(unique_jobs)}个岗位")
        print(f"📄 已保存: {filename}")
        
        return unique_jobs


if __name__ == '__main__':
    collector = NBUJobCollector()
    collector.collect_all()
