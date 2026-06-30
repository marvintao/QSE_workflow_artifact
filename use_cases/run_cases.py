"""顺序跑 use_cases/requirements/req_txt/req_{id}.txt 列出的若干用例。

通过本地 backend(默认 http://127.0.0.1:8000)POST /request 提交需求,
然后轮询 GET /trace/{rid} 直到 final_status 落定,逐个进度打印。

用法:
    python use_cases/run_cases.py 0 10 20 21
"""
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent
REQ_DIR = ROOT / "requirements" / "req_txt"
POLL_INTERVAL = 1.5         # 每 1.5 秒拉一次 trace
MAX_WAIT_S = 30 * 60        # 单个用例最长等 30 分钟


def post_request(raw_text: str, language: str = "en") -> str:
    """提交需求,返回 request_id。后端立刻返回 rid,流水线后台跑。"""
    body = json.dumps({"raw_text": raw_text, "language": language}).encode()
    req = urllib.request.Request(
        f"{BASE}/request", data=body, method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["request_id"]


def get_trace(rid: str) -> dict:
    with urllib.request.urlopen(f"{BASE}/trace/{rid}", timeout=30) as r:
        return json.loads(r.read())


def run_one(req_id: int) -> dict:
    """跑一个 req_{id}.txt,返回 {req_id, rid, final, verify, stages, duration_s, last_error}。"""
    txt_path = REQ_DIR / f"req_{req_id}.txt"
    raw_text = txt_path.read_text(encoding="utf-8", errors="replace")
    print(f"\n┌─ req_{req_id} ({txt_path.name}, {len(raw_text)} chars)")
    t0 = time.monotonic()
    try:
        rid = post_request(raw_text)
    except Exception as e:
        print(f"│  POST failed: {type(e).__name__}: {e}")
        return {"req_id": req_id, "rid": None, "final": "post_error",
                "verify": None, "stages": 0, "duration_s": 0,
                "last_error": str(e)}
    print(f"│  rid = {rid}")
    seen_stages: set[str] = set()
    last_error = None
    while True:
        elapsed = time.monotonic() - t0
        if elapsed > MAX_WAIT_S:
            print(f"│  ✗ TIMEOUT after {elapsed:.0f}s, abandoning poll")
            return {"req_id": req_id, "rid": rid, "final": "timeout",
                    "verify": None, "stages": len(seen_stages),
                    "duration_s": int(elapsed), "last_error": "timeout"}
        try:
            tr = get_trace(rid)
        except Exception as e:
            print(f"│  trace fetch failed: {type(e).__name__}: {e}")
            time.sleep(POLL_INTERVAL)
            continue
        # 打印新出现的 stage(按出现顺序)
        for s in tr["stages"]:
            key = f"{s['stage']}#{s['attempt']}"
            if key in seen_stages:
                continue
            seen_stages.add(key)
            art = s.get("artifact") or {}
            err = art.get("error_type")
            if err:
                last_error = f"{s['stage']}: {err}: {art.get('error_message','')[:200]}"
                print(f"│  ⚠ {s['stage']:<10} attempt={s['attempt']}  "
                      f"{(s['duration_ms'] or 0)/1000:>5.1f}s  ← {err}")
            else:
                print(f"│  ✓ {s['stage']:<10} attempt={s['attempt']}  "
                      f"{(s['duration_ms'] or 0)/1000:>5.1f}s")
        if tr["request"]["final_status"] is not None:
            final = tr["request"]["final_status"]
            verify = tr["request"]["verification_status"]
            dur = int(time.monotonic() - t0)
            mark = "✓" if final == "success" else "✗"
            print(f"└─ {mark} final={final} verify={verify} {dur}s\n")
            return {"req_id": req_id, "rid": rid, "final": final,
                    "verify": verify, "stages": len(seen_stages),
                    "duration_s": dur, "last_error": last_error}
        time.sleep(POLL_INTERVAL)


def main() -> int:
    ids = [int(x) for x in sys.argv[1:]] or [0, 10, 20, 21]
    print(f"=== Running {len(ids)} use cases: {ids} ===")
    print(f"=== Backend: {BASE}  Polling every {POLL_INTERVAL}s ===")
    overall_t0 = time.monotonic()
    results = []
    for rid in ids:
        results.append(run_one(rid))
    overall_dur = int(time.monotonic() - overall_t0)
    print(f"\n=== Summary (total {overall_dur}s = {overall_dur/60:.1f}min) ===")
    print(f"{'req_id':<8} {'final':<10} {'verify':<14} "
          f"{'stages':<7} {'dur(s)':<7} last_error")
    print("-" * 80)
    for r in results:
        err = (r.get("last_error") or "")[:60]
        print(f"req_{r['req_id']:<4} {str(r['final']):<10} "
              f"{str(r.get('verify') or '-'):<14} {r['stages']:<7} "
              f"{r['duration_s']:<7} {err}")
    succ = sum(1 for r in results if r["final"] == "success")
    print(f"\n=== {succ}/{len(results)} success ===")
    return 0 if succ == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
