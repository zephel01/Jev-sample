"""実験ランナー。JSONL に追記し、既存キーはスキップして再開できる。

使い方:
  python3 run.py latency --site mac --n 50
  python3 run.py route   --site mac --lang ja --noise clean --method direct
  python3 run.py route   --site mac --all
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import jev
import scenarios

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
_lock = threading.Lock()


def log_path(kind, site):
    return os.path.join(LOG_DIR, f"{kind}_{site}.jsonl")


def done_keys(path):
    keys = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    keys.add(json.loads(line)["key"])
                except Exception:  # noqa: BLE001
                    pass
    return keys


def write(path, rec):
    with _lock:
        with open(path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()


def cmd_latency(args, key):
    path = log_path("latency", args.site)
    seen = done_keys(path)
    state = ("コーディングエージェントへの作業依頼。core/retry.go の withRetry のほうで、"
             "上限を3回から5回にする。手元のブランチで作業して、差分だけ見せてくれればいい。")
    specs = {
        "choice": jev.direct_questions("ja"),
        "noul1": {"q": {"type": "noul", "instructions": jev.NOUL_JA["irreversible"]}},
        "noul4": jev.decomposed_questions("ja"),
        "score": {"q": {"type": "score",
                        "instructions": "この依頼の作業規模はどの程度か。",
                        "criteria": ["数行で終わる", "1ファイル内で収まる", "複数の層にまたがる"]}},
    }
    n = 0
    for name, qs in specs.items():
        for i in range(args.n):
            k = f"lat|{name}|{i}"
            if k in seen:
                continue
            a, u, ms, err = jev.ask(key, state, qs)
            write(path, {"key": k, "kind": name, "i": i, "ms": round(ms, 1),
                         "usage": u, "err": err, "ts": time.time()})
            n += 1
            if err:
                print(f"  ERR {k}: {err}", file=sys.stderr)
    print(f"latency: {n} new calls -> {path}")


def route_jobs(args):
    rows = scenarios.build()
    langs = ["ja", "en"] if args.all else [args.lang]
    noises = ["clean", "noisy"] if args.all else [args.noise]
    methods = ["direct", "decomposed"] if args.all else [args.method]
    jobs = []
    for r in rows:
        for lang in langs:
            for noise in noises:
                field = f"text_{lang}" + ("_noisy" if noise == "noisy" else "")
                for m in methods:
                    jobs.append((f"{r['id']}|{lang}|{noise}|{m}", r, lang, noise, m, r[field]))
    return jobs


def cmd_route(args, key):
    path = log_path("route", args.site)
    seen = done_keys(path)
    jobs = [j for j in route_jobs(args) if j[0] not in seen]
    if args.limit:
        jobs = jobs[:args.limit]
    print(f"route: {len(jobs)} calls to run (site={args.site}, workers={args.workers})")
    done = [0]

    def one(job):
        k, r, lang, noise, method, text = job
        qs = jev.direct_questions(lang) if method == "direct" else jev.decomposed_questions(lang)
        a, u, ms, err = jev.ask(key, text, qs)
        rec = {"key": k, "id": r["id"], "label": r["label"], "attrs": r["attrs"],
               "lang": lang, "noise": noise, "method": method,
               "ms": round(ms, 1), "usage": u, "err": err, "ts": time.time()}
        if a and method == "direct":
            q = a.get("q", {})
            rec["pred"] = q.get("choice")
            rec["confidence"] = q.get("confidence")
            rec["probabilities"] = q.get("probabilities")
        elif a:
            nouls = {kk: vv.get("noul") for kk, vv in a.items()}
            rec["nouls"] = nouls
            rec["pred"] = jev.compose(nouls)
        write(path, rec)
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"  {done[0]}/{len(jobs)}", flush=True)
        if err:
            print(f"  ERR {k}: {err}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(one, jobs))
    print(f"route: done -> {path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["latency", "route"])
    p.add_argument("--site", required=True, help="mac or cloud")
    p.add_argument("--key-file", default=None)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--lang", default="ja")
    p.add_argument("--noise", default="clean")
    p.add_argument("--method", default="direct")
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()
    key = jev.load_key(args.key_file)
    if args.cmd == "latency":
        args.workers = 1
        cmd_latency(args, key)
    else:
        cmd_route(args, key)


if __name__ == "__main__":
    main()
