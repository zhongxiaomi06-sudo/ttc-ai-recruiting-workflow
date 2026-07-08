#!/usr/bin/env python3
"""TalentMatch 全功能审计 — 50轮连续测试"""
import urllib.request, json, sys, os, time, re

BASE = os.environ.get("TARGET_URL", "https://yorkteam.cn")
INTERNAL = "http://127.0.0.1:8878"

class Auditor:
    def __init__(self):
        self.round = 0
        self.total = 0
        self.passed = 0
        self.failed = []
        self.token = None
        
    def check(self, label, url, method="GET", body=None, expect_status=200, validate=None):
        self.total += 1
        try:
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            req = urllib.request.Request(url, headers=headers, 
                data=json.dumps(body).encode() if body and method=="POST" else None,
                method=method)
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
            if resp.status != expect_status:
                self._fail(label, f"HTTP {resp.status} (expected {expect_status})")
                return
            if validate and not validate(data):
                self._fail(label, "validation failed")
                return
            self.passed += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            self._fail(label, f"HTTP {e.code}: {body}")
        except Exception as e:
            self._fail(label, f"{type(e).__name__}: {e}")
    
    def _fail(self, label, reason):
        self.failed.append(f"R{self.round} {label}: {reason}")
    
    def run_round(self, r):
        self.round = r
        errors_before = self.passed
        
        # Phase 1: 核心健康检查
        self.check("health", f"{INTERNAL}/health",
            validate=lambda d: d.get("status") == "ok")
        self.check("stats", f"{INTERNAL}/api/stats",
            validate=lambda d: d.get("candidates", -1) >= 0)
        self.check("candidates", f"{INTERNAL}/api/candidates?limit=5",
            validate=lambda d: isinstance(d, (list, dict)))
        self.check("jobs", f"{INTERNAL}/api/jobs?limit=5",
            validate=lambda d: isinstance(d, (list, dict)))
        
        # Phase 2: 认证
        self.check("register", f"{INTERNAL}/api/auth/register", method="POST",
            body={"username": f"test_r{r}", "password": "Test123456", "display_name": f"Tester{r}", "role": "猎头顾问"},
            validate=lambda d: len(d.get("token","")) > 10)
        
        login = urllib.request.Request(f"{INTERNAL}/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"username": f"test_r{r}", "password": "Test123456"}).encode(),
            method="POST")
        resp = json.loads(urllib.request.urlopen(login).read())
        self.token = resp.get("token", "")
        
        self.check("me_bearer", f"{INTERNAL}/api/auth/me",
            validate=lambda d: d.get("username", "") == f"test_r{r}")
        
        # Phase 3: 搜索
        self.check("search_python", f"{INTERNAL}/api/candidates/search/Python",
            validate=lambda d: isinstance(d, list))
        self.check("search_product", f"{INTERNAL}/api/candidates/search/产品",
            validate=lambda d: isinstance(d, list))
        
        # Phase 4: 匹配
        self.check("fast_match", f"{INTERNAL}/api/fast-match", method="POST",
            body={"jd_text": "Python后端工程师 3年经验 Django MySQL", "limit": 10},
            validate=lambda d: isinstance(d.get("matches"), list))
        self.check("match_rules", f"{INTERNAL}/api/match-rules",
            validate=lambda d: isinstance(d, dict))
        self.check("history", f"{INTERNAL}/api/history?limit=5",
            validate=lambda d: isinstance(d, list))
        
        # Phase 5: 追踪
        self.check("track_event", f"{INTERNAL}/api/tracking/event", method="POST",
            body={"entity_type":"candidate","entity_id":"test","event_type":"view","user_id":"test","duration":5},
            validate=lambda d: d.get("status") == "ok")
        self.check("track_batch", f"{INTERNAL}/api/tracking/batch", method="POST",
            body=[{"entity_type":"candidate","entity_id":"test2","event_type":"view","duration":3}],
            validate=lambda d: d.get("status") == "ok")
        self.check("track_stats", f"{INTERNAL}/api/tracking/stats",
            validate=lambda d: d.get("total", -1) >= 0)
        
        # Phase 6: 反馈
        self.check("feedback_post", f"{INTERNAL}/api/feedback", method="POST",
            body={"entity_type":"match","entity_id":"test","feedback_type":"like","feedback_text":"good"},
            validate=lambda d: d.get("status") == "ok")
        self.check("feedback_stats", f"{INTERNAL}/api/feedback/stats",
            validate=lambda d: d.get("total", -1) >= 0)
        
        # Phase 7: Analytics
        for ana in ["industry", "skill", "source", "salary", "education"]:
            self.check(f"analytics_{ana}", f"{INTERNAL}/api/analytics/{ana}",
                validate=lambda d: isinstance(d, list))
        
        # Phase 8: 消息
        self.check("messages", f"{INTERNAL}/api/messages",
            validate=lambda d: isinstance(d, list) or "items" in d)
        self.check("messages_unread", f"{INTERNAL}/api/messages/unread?user_id=test",
            validate=lambda d: "count" in d)
        
        # Phase 9: 职位
        self.check("job_detail", f"{INTERNAL}/api/jobs/stats",
            validate=lambda d: isinstance(d, dict))
        
        return self.passed - errors_before
    
    def report(self):
        print(f"\n{'='*60}")
        print(f"TalentMatch 审计完成: {self.passed}/{self.total} PASS")
        if self.failed:
            print(f"\n失败项 ({len(self.failed)}):")
            for f in self.failed:
                print(f"  ❌ {f}")
        else:
            print("\n✅ 全部通过!")
        return self.passed == self.total

if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    a = Auditor()
    print(f"Starting {rounds}-round audit on {BASE}")
    start = time.time()
    for r in range(1, rounds + 1):
        ok = a.run_round(r)
        if r % 10 == 0:
            print(f"  Round {r}/{rounds} — {a.passed}/{a.total} passed")
    elapsed = time.time() - start
    success = a.report()
    print(f"\n耗时: {elapsed:.1f}s 每轮: {elapsed/rounds:.2f}s")
    sys.exit(0 if success else 1)
