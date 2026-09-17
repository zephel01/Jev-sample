"""TypeSafe Jev の最小クライアント（標準ライブラリのみ）。"""
import json
import os
import ssl
import time
import urllib.error
import urllib.request

API = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
KEY_FILE_DEFAULT = os.path.expanduser("~/.typesafe/key")


def load_key(path=None):
    k = os.environ.get("TYPESAFE_API_KEY")
    if k:
        return k.strip()
    p = path or KEY_FILE_DEFAULT
    with open(p) as f:
        return f.read().strip()


_CTX = ssl.create_default_context()
_CA = "/root/.ccr/ca-bundle.crt"
if os.path.exists(_CA):
    try:
        _CTX.load_verify_locations(_CA)
    except Exception:
        pass


def ask(key, state, questions, timeout=60, retries=4):
    """1リクエスト送る。(answers, usage, elapsed_ms, err) を返す。"""
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(API, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        })
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                raw = r.read()
            ms = (time.perf_counter() - t0) * 1000
            d = json.loads(raw)
            return d.get("answers", {}), d.get("usage", {}), ms, None
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            last = f"HTTP {e.code}: {detail}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8) + 0.3 * attempt)
                continue
            return None, None, (time.perf_counter() - t0) * 1000, last
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(min(2 ** attempt, 8))
    return None, None, 0.0, last


# ---------------- 実験用の質問定義（閾値と質問は1か所に置く） ----------------
LABELS = ["haiku_inline", "opus_subagent", "external_harness", "ask_user"]

CHOICE_CRITERIA_JA = {
    "haiku_inline": "小さく機械的な変更で、その場で軽量モデルに直させればよい",
    "opus_subagent": "実装の方針そのものを選ぶ判断が必要で、上位モデルのサブエージェントに渡すべき",
    "external_harness": "変更が複数の箇所にまたがるか作業量が大きく、長時間動く外部ハーネスに任せるべき",
    "ask_user": "着手に必要な情報が足りないか、取り消しの効かない操作を含むので、依頼者に確認すべき",
}
CHOICE_CRITERIA_EN = {
    "haiku_inline": "A small mechanical edit; a lightweight model can do it inline",
    "opus_subagent": "The implementation approach itself must be chosen; hand it to a stronger sub-agent",
    "external_harness": "The change spans several places or the work is large; hand it to a long-running external harness",
    "ask_user": "Information needed to start is missing, or it includes an irreversible operation, so ask the requester",
}
CHOICE_INSTR_JA = "コーディングエージェントへの作業依頼である。この依頼をどの実行先に渡すべきか。"
CHOICE_INSTR_EN = ("This is a work request for a coding agent. "
                   "Which execution target should this request be handed to?")

NOUL_JA = {
    "info": ("着手に必要な対象が依頼の中で特定できるか。具体的には、どのファイルまたはどの箇所を"
             "変更するのか、どういう条件にするのかが依頼文から読み取れる場合に yes。"
             "対象や環境や仕様が未定で、作業者側が決める必要がある場合は no。"),
    "irreversible": ("依頼された作業に、取り消しの効かない操作が含まれるか。本番データの削除や変更、"
                     "認証情報の削除、main ブランチへの force push、本番マイグレーションの実行などが"
                     "含まれる場合は yes。手元のブランチでの作業や差分の提示だけなら no。"),
    "design": ("実装の方針そのものを選ぶ判断を、作業者が決める必要があるか。どの方式を採るか、"
               "どのレイヤーに置くか、同期か非同期かといった設計上の選択が依頼者から委ねられている"
               "場合は yes。既存のやり方を踏襲するよう指示されている場合は no。"),
    "broad": ("変更が複数のファイルや層にまたがるか、または相当量の実装作業を伴うか。3箇所以上への"
              "同じ変更、呼び出し側すべての修正、テストやドキュメントや移行スクリプトまで含む仕上げが"
              "求められている場合は yes。1ファイル内で数行に収まる場合は no。"),
}
NOUL_EN = {
    "info": ("Can the target needed to start be identified from the request? Yes if the request says "
             "which file or place to change and what the new behavior should be. No if the target, "
             "the environment, or the spec is undecided and the worker has to decide it."),
    "irreversible": ("Does the requested work include an irreversible operation? Yes if it includes "
                     "deleting or changing production data, deleting credentials, force pushing to main, "
                     "or running a production migration. No if it is work on a local branch or just showing a diff."),
    "design": ("Does the worker have to choose the implementation approach itself? Yes if the requester "
               "leaves a design choice open, such as which approach to take, which layer it belongs in, "
               "or sync versus async. No if the request says to follow the existing approach."),
    "broad": ("Does the change span multiple files or layers, or involve a substantial amount of work? "
              "Yes if the same change is needed in three or more places, every call site must be fixed, "
              "or tests, docs, or a migration script are part of the deliverable. "
              "No if it fits in a few lines inside one file."),
}


def direct_questions(lang):
    return {"q": {
        "type": "choice",
        "instructions": CHOICE_INSTR_JA if lang == "ja" else CHOICE_INSTR_EN,
        "criteria": CHOICE_CRITERIA_JA if lang == "ja" else CHOICE_CRITERIA_EN,
    }}


def decomposed_questions(lang):
    src = NOUL_JA if lang == "ja" else NOUL_EN
    return {k: {"type": "noul", "instructions": v} for k, v in src.items()}


def compose(nouls, thr=0.5):
    """前提条件チェックの答えから、生成器と同じルールでラベルを決める。"""
    info = nouls.get("info", 0.0) >= thr
    irrev = nouls.get("irreversible", 0.0) >= thr
    design = nouls.get("design", 0.0) >= thr
    broad = nouls.get("broad", 0.0) >= thr
    if (not info) or irrev:
        return "ask_user"
    if design:
        return "opus_subagent"
    if broad:
        return "external_harness"
    return "haiku_inline"
