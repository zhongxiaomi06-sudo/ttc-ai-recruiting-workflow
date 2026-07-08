#!/usr/bin/env python3
"""白屏守护 — 每次部署后跑 5 个检查，任一失败=不可交付"""
import urllib.request, json, sys, os, re

BASE = os.environ.get("TARGET_URL", "https://yorkteam.cn")

CHECKS = [
    ("HTML",      "/",           200, lambda b: b"<div id=\"root\">" in b and b"<script" in b),
    ("health",    "/health",     200, lambda b: json.loads(b).get("status") == "ok"),
    ("stats",     "/api/stats",  200, lambda b: json.loads(b).get("candidates", -1) >= 0),
    ("candidates","/api/candidates?limit=3", 200, lambda b: isinstance(json.loads(b), (list, dict))),
    ("jobs",      "/api/jobs?status=active&limit=3", 200, lambda b: isinstance(json.loads(b), (list, dict))),
]

def main():
    print(f"🛡️  WhiteScreen Guard — {BASE}\n")
    failed = 0
    for name, path, expect_status, validate in CHECKS:
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": "WSGuard/1.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            body = resp.read()
            if resp.status != expect_status:
                print(f"❌ {name}: HTTP {resp.status} (expected {expect_status})")
                failed += 1
            elif not validate(body):
                print(f"❌ {name}: validation failed ({len(body)} bytes)")
                failed += 1
            else:
                print(f"✅ {name}: OK ({len(body)} bytes)")
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed += 1
    
    # JS check
    html = urllib.request.urlopen(BASE + "/").read()
    m = re.search(rb'/assets/(index-[A-Za-z0-9_-]+\.js)', html)
    if m:
        try:
            js_url = BASE + "/assets/" + m.group(1).decode()
            js_resp = urllib.request.urlopen(js_url)
            print(f"✅ JS: {m.group(1).decode()} ({len(js_resp.read())} bytes)")
        except Exception as e:
            print(f"❌ JS: {e}")
            failed += 1
    
    print(f"\n{'✅ ALL PASS' if failed == 0 else f'❌ {failed} FAILURES — DO NOT DELIVER'}")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
