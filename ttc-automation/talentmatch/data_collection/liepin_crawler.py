"""
猎聘简历采集器 - 后台直接调API版
原理：浏览器登录猎聘后，导出cookie → 用这个脚本直接调猎聘API拿数据
不需要打开浏览器，跑在服务器上就能批量采集

使用方法：
  1. 在Chrome登录猎聘
  2. 安装 EditThisCookie 插件导出Cookie
  3. 把cookie字符串填入下面的 COOKIE_STR
  4. python3 liepin_crawler.py --search "产品经理" --pages 5
"""

import requests
import json
import time
import re
import random
from typing import Optional, Dict, List
from urllib.parse import quote, urlencode
from datetime import datetime
import os

# =============================================
# 猎聘API端点（从企业插件拦截到的XHR发现）
# =============================================
LIEPIN_API = {
    # 搜索简历列表
    'search_resume': 'https://www.liepin.com/a/search-api/v1/resume/search',
    # 简历详情（需要resId）
    'resume_detail': 'https://www.liepin.com/a/resume-api/v1/resume/get-resume-detail',
    # 联系方式（需要resId）
    'contact_info': 'https://www.liepin.com/a/resume-api/v1/resume/get-contact-info',
    # 批量搜索
    'batch_search': 'https://www.liepin.com/a/search-api/v1/resume/batch-search',
}

class LiepinCrawler:
    """猎聘简历采集器"""
    
    def __init__(self, cookie_str: str = ""):
        self.session = requests.Session()
        
        # 从企业插件源码学到的：猎聘API需要的请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.liepin.com/zhaopin/',
            'Origin': 'https://www.liepin.com',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
        })
        
        if cookie_str:
            self.set_cookies(cookie_str)
    
    def set_cookies(self, cookie_str: str):
        """设置Cookie（从浏览器导出）"""
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.session.cookies.set(key.strip(), value.strip(), domain='.liepin.com')
    
    def set_cookies_from_dict(self, cookies: Dict):
        """从字典设置Cookie"""
        for key, value in cookies.items():
            self.session.cookies.set(key, value, domain='.liepin.com')
    
    def search_resumes(self, keyword: str, page: int = 1, page_size: int = 20, 
                       city: str = "", salary: str = "", education: str = "") -> Optional[dict]:
        """
        搜索简历列表
        - keyword: 搜索关键词（职位名/技能）
        - page: 页码
        - page_size: 每页数量
        - city: 城市编码（如"110000"=北京）
        - salary: 薪资范围（如"10-20"）
        - education: 学历要求
        """
        params = {
            'key': keyword,
            'currentPage': page,
            'pageSize': page_size,
            'scene': 'search',
        }
        if city: params['city'] = city
        if salary: params['salary'] = salary
        if education: params['education'] = education
        
        try:
            resp = self.session.get(
                LIEPIN_API['search_resume'],
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0 or data.get('success'):
                    return data
                else:
                    print(f"❌ API返回错误: {data}")
                    return None
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    def get_resume_detail(self, res_id: str) -> Optional[dict]:
        """获取简历详情"""
        params = {'resId': res_id}
        try:
            resp = self.session.get(
                LIEPIN_API['resume_detail'],
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"❌ 获取详情失败 {res_id}: {e}")
            return None
    
    def get_contact_info(self, res_id: str) -> Optional[dict]:
        """获取联系方式（电话/邮箱）"""
        params = {'resId': res_id}
        try:
            resp = self.session.get(
                LIEPIN_API['contact_info'],
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"❌ 获取联系方式失败 {res_id}: {e}")
            return None
    
    def batch_collect(self, keyword: str, max_pages: int = 5, 
                      delay: float = 2.0, save_to: str = ""):
        """
        批量采集
        - keyword: 搜索关键词
        - max_pages: 最大翻页数
        - delay: 每次请求间隔（秒）
        - save_to: 保存路径，为空则打印结果
        """
        all_resumes = []
        total = 0
        
        print(f"\n🔍 开始采集: '{keyword}' 共{max_pages}页")
        
        for page in range(1, max_pages + 1):
            print(f"\n📄 第{page}页...")
            
            result = self.search_resumes(keyword, page=page)
            if not result:
                print(f"❌ 第{page}页获取失败，停止")
                break
            
            # 从企业插件源码看到猎聘返回结构
            data_list = (result.get('data', {})
                        .get('dataList', []) or 
                        result.get('data', []) or 
                        result.get('list', []))
            
            if not data_list:
                print(f"📭 第{page}页没有数据")
                break
            
            print(f"  找到 {len(data_list)} 个候选人")
            
            # 逐个获取详情和联系方式
            for idx, item in enumerate(data_list):
                res_id = item.get('resId') or item.get('resIdEncode')
                name = item.get('name', '未知')
                print(f"  [{page}.{idx+1}] {name} (resId: {res_id})")
                
                if res_id:
                    time.sleep(delay)  # 延迟，防封
                    
                    # 获取详情
                    detail = self.get_resume_detail(res_id)
                    if detail:
                        item['_detail'] = detail.get('data', {})
                    
                    time.sleep(delay * 0.5)
                    
                    # 获取联系方式
                    contact = self.get_contact_info(res_id)
                    if contact:
                        item['_contact'] = contact.get('data', {})
                        phone = item['_contact'].get('phone', '')
                        email = item['_contact'].get('email', '')
                        if phone:
                            print(f"    📞 {phone}")
                        if email:
                            print(f"    📧 {email}")
                
                all_resumes.append(item)
                total += 1
            
            # 页间延迟
            if page < max_pages:
                wait = delay * 3
                print(f"  ⏳ 等待{wait:.0f}秒后翻页...")
                time.sleep(wait)
        
        # 保存结果
        output = {
            'keyword': keyword,
            'total': total,
            'pages': page,
            'timestamp': datetime.now().isoformat(),
            'resumes': all_resumes
        }
        
        if save_to:
            filename = save_to
        else:
            filename = f"liepin_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 采集完成！共{total}条简历，已保存到: {filename}")
        return output
    
    def parse_to_candidate(self, raw: dict) -> dict:
        """把猎聘原始数据解析成TalentMatch候选人格式"""
        candidate = {}
        
        # 基本信息
        candidate['name'] = raw.get('name', '')
        candidate['title'] = raw.get('title', '') or raw.get('jobTitle', '')
        candidate['current_company'] = raw.get('company', '') or raw.get('currentCompany', '')
        candidate['salary_expect'] = raw.get('salary', '') or raw.get('expectSalary', '')
        candidate['work_experience_years'] = raw.get('workExpire', '') or raw.get('workYears', 0)
        candidate['education_level'] = raw.get('education', '') or raw.get('maxDegree', '')
        
        # 联系方式
        contact = raw.get('_contact', {})
        candidate['phone'] = contact.get('phone', '')
        candidate['email'] = contact.get('email', '')
        
        # 工作经历
        detail = raw.get('_detail', {})
        work_exps = detail.get('workExperiences', []) or raw.get('workExperiences', [])
        if work_exps:
            candidate['work_experiences'] = [{
                'company': exp.get('companyName', ''),
                'title': exp.get('positionName', ''),
                'start': exp.get('startTime', ''),
                'end': exp.get('endTime', ''),
                'description': exp.get('jobDescription', ''),
            } for exp in work_exps]
        
        # 教育经历
        edu_exps = detail.get('educations', []) or raw.get('educations', [])
        if edu_exps:
            candidate['educations'] = [{
                'school': edu.get('schoolName', ''),
                'major': edu.get('major', ''),
                'degree': edu.get('degree', ''),
                'start': edu.get('startTime', ''),
                'end': edu.get('endTime', ''),
            } for edu in edu_exps]
        
        # 技能
        skills = detail.get('skills', []) or raw.get('skills', [])
        if skills:
            candidate['skills'] = [s.get('name', '') if isinstance(s, dict) else s for s in skills]
        
        # 原数据保留
        candidate['_raw'] = raw
        
        return candidate


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='猎聘简历采集器')
    parser.add_argument('--search', '-s', required=True, help='搜索关键词')
    parser.add_argument('--pages', '-p', type=int, default=3, help='翻页数')
    parser.add_argument('--delay', '-d', type=float, default=2.0, help='请求间隔(秒)')
    parser.add_argument('--cookie', '-c', help='Cookie字符串')
    parser.add_argument('--output', '-o', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 优先从环境变量读cookie
    cookie = args.cookie or os.environ.get('LIEPIN_COOKIE', '')
    
    if not cookie:
        print("=" * 50)
        print("⚠️  需要猎聘Cookie才能运行")
        print("=" * 50)
        print("请先在Chrome登录猎聘 → F12 → Application → Cookies")
        print("复制整个Cookie字符串，然后:")
        print(f"  python3 liepin_crawler.py -s '{args.search}' -p {args.pages} -c '你的cookie'")
        print("或者设置环境变量: export LIEPIN_COOKIE='你的cookie'")
        print("=" * 50)
        return
    
    crawler = LiepinCrawler(cookie)
    crawler.batch_collect(
        keyword=args.search,
        max_pages=args.pages,
        delay=args.delay,
        save_to=args.output
    )


if __name__ == '__main__':
    main()
