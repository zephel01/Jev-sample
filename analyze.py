"""集計。logs/*.jsonl を読んで、正解率・レイテンシ・校正・コストを出す。"""
import collections
import json
import os
import statistics
import sys

import jev

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000  # $0.042 / 1M input tokens, output free


def load(kind, site):
    p = os.path.join(HERE, "logs", f"{kind}_{site}.jsonl")
    if not os.path.exists(p):
        return []
    out, seen = [], set()
    for line in open(p):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        out.append(r)
    return out


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(round(q / 100 * (len(xs) - 1)))))
    return xs[i]


def latency_report(sites):
    print("\n## レイテンシ（往復込み、直列）")
    print("site  kind    n    p50     p95     p99     mean   in_tok")
    for site in sites:
        rows = [r for r in load("latency", site) if not r.get("err")]
        for kind in ["choice", "noul1", "noul4", "score"]:
            xs = [r["ms"] for r in rows if r["kind"] == kind]
            tk = [r["usage"]["input_tokens"] for r in rows if r["kind"] == kind and r.get("usage")]
            if not xs:
                continue
            print(f"{site:5} {kind:6} {len(xs):4} {pct(xs,50):7.1f} {pct(xs,95):7.1f} "
                  f"{pct(xs,99):7.1f} {statistics.mean(xs):7.1f} {statistics.mean(tk):6.0f}")


def acc(rows):
    ok = sum(1 for r in rows if r.get("pred") == r["label"])
    return ok / len(rows) if rows else float("nan"), len(rows)


def route_report(sites):
    for site in sites:
        rows = [r for r in load("route", site) if not r.get("err") and r.get("pred")]
        if not rows:
            continue
        print(f"\n## 正解率（site={site}, n={len(rows)}）")
        print("lang noise method       n    正解率   p50ms   in_tok/件")
        for lang in ["ja", "en"]:
            for noise in ["clean", "noisy"]:
                for method in ["direct", "decomposed"]:
                    sel = [r for r in rows if r["lang"] == lang and r["noise"] == noise
                           and r["method"] == method]
                    if not sel:
                        continue
                    a, n = acc(sel)
                    ms = pct([r["ms"] for r in sel], 50)
                    tk = statistics.mean([r["usage"]["input_tokens"] for r in sel if r.get("usage")])
                    print(f"{lang:4} {noise:5} {method:11} {n:4} {a*100:7.1f}% {ms:7.1f} {tk:9.0f}")

        print(f"\n### 混同（site={site}, ja/clean）")
        for method in ["direct", "decomposed"]:
            sel = [r for r in rows if r["lang"] == "ja" and r["noise"] == "clean"
                   and r["method"] == method]
            cm = collections.Counter((r["label"], r["pred"]) for r in sel)
            print(f" [{method}] 正解ラベル -> 予測（誤りのみ）")
            for (t, p), c in sorted(cm.items(), key=lambda x: -x[1]):
                if t != p:
                    print(f"   {t:17} -> {p:17} {c}")

        print(f"\n### 校正（site={site}, direct, confidence 帯ごとの実正解率）")
        sel = [r for r in rows if r["method"] == "direct" and r.get("confidence") is not None]
        bins = collections.defaultdict(list)
        for r in sel:
            b = min(9, int(r["confidence"] * 10))
            bins[b].append(r["pred"] == r["label"])
        print(" 帯        n    実正解率")
        for b in sorted(bins):
            v = bins[b]
            print(f" {b/10:.1f}-{(b+1)/10:.1f} {len(v):5} {sum(v)/len(v)*100:7.1f}%")

        print(f"\n### 保留にした場合（site={site}, direct, ja/clean）")
        sel = [r for r in rows if r["method"] == "direct" and r["lang"] == "ja"
               and r["noise"] == "clean" and r.get("confidence") is not None]
        for thr in [0.0, 0.5, 0.7, 0.8, 0.9, 0.95]:
            auto = [r for r in sel if r["confidence"] >= thr]
            if not auto:
                continue
            a, n = acc(auto)
            print(f" 閾値 {thr:.2f}: 自動処理 {n/len(sel)*100:5.1f}%  その中の正解率 {a*100:5.1f}%  "
                  f"保留 {(1-n/len(sel))*100:5.1f}%")

        tot_tok = sum(r["usage"]["input_tokens"] for r in rows if r.get("usage"))
        lat = [r for r in load("latency", site) if r.get("usage")]
        tot_tok += sum(r["usage"]["input_tokens"] for r in lat)
        print(f"\n### コスト（site={site}）")
        print(f" リクエスト数 {len(rows)+len(lat)}、入力トークン {tot_tok:,}、"
              f"概算 ${tot_tok*PRICE_PER_INPUT_TOKEN:.4f}（出力は無料）")


def noul_threshold_sweep(sites):
    print("\n## 合成ルールの閾値を振る（decomposed, ja/clean）")
    for site in sites:
        rows = [r for r in load("route", site)
                if not r.get("err") and r.get("nouls") and r["lang"] == "ja" and r["noise"] == "clean"]
        if not rows:
            continue
        print(f" site={site}")
        for thr in [0.3, 0.4, 0.5, 0.6, 0.7]:
            ok = sum(1 for r in rows if jev.compose(r["nouls"], thr) == r["label"])
            print(f"  thr={thr}: {ok/len(rows)*100:5.1f}%  (n={len(rows)})")


if __name__ == "__main__":
    sites = sys.argv[1:] or ["mac", "cloud"]
    latency_report(sites)
    route_report(sites)
    noul_threshold_sweep(sites)
