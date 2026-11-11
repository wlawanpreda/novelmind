#!/usr/bin/env python3
"""
log_report.py — สรุปสุขภาพ pipeline จาก SecondBrain/logs/events.jsonl
    python log_report.py            # 7 วันล่าสุด
    python log_report.py --days 30
    python log_report.py --failures # แสดง output ท้ายๆ ของ stage ที่ล้มล่าสุด
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from run_log import read_events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--failures", action="store_true")
    args = ap.parse_args()

    since = datetime.now() - timedelta(days=args.days)
    stats = defaultdict(lambda: {"runs": 0, "fail": 0, "skip": 0, "secs": 0.0, "last_fail": None})
    fails = []
    cycles = 0
    for e in read_events(since):
        if e["kind"] == "cycle_end":
            cycles += 1
        if e["kind"] != "stage":
            continue
        s = stats[e["stage"]]
        if e.get("skipped"):
            s["skip"] += 1
            continue
        s["runs"] += 1
        s["secs"] += float(e.get("duration_s", 0))
        if not e.get("ok"):
            s["fail"] += 1
            s["last_fail"] = e["ts"]
            fails.append(e)

    if not stats:
        print(f"ยังไม่มี event ใน {args.days} วันล่าสุด (events.jsonl จะเริ่มสะสมเมื่อ orchestrator รันรอบถัดไป)")
        return

    print(f"\nสรุป {args.days} วันล่าสุด • {cycles} รอบ\n")
    print(f"{'stage':<18}{'runs':>6}{'fail':>6}{'fail%':>7}{'avg(s)':>9}{'skip':>6}  last_fail")
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1]["fail"]):
        pct = 100 * s["fail"] / s["runs"] if s["runs"] else 0
        avg = s["secs"] / s["runs"] if s["runs"] else 0
        print(f"{name:<18}{s['runs']:>6}{s['fail']:>6}{pct:>6.0f}%{avg:>9.1f}{s['skip']:>6}  {s['last_fail'] or '-'}")

    if args.failures and fails:
        print("\n--- ความล้มเหลวล่าสุด ---")
        for e in fails[-5:]:
            print(f"\n[{e['ts']}] {e['stage']} rc={e.get('rc')}\n{e.get('output_tail', '')}")


if __name__ == "__main__":
    main()
