#!/usr/bin/env python3
"""quange-judgment 规则版答题器（零依赖，公开仓库自带）。

读 docs/criteria.json 的 10 条冻结判据，输出结构化结果 + 五段人话。
未接本地语料时一律标 criteria_only / is_inference=true，绝不冒充本人原话。
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = "与本人无关、非本人授权、非本人观点；不构成投资建议"


def norm(s):
    return re.sub(r"[\s\W_]+", "", s.lower())


def bigrams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def sim(a, b):
    x, y = bigrams(a), bigrams(b)
    return len(x & y) / len(x) if x else 0.0


def load(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d["criteria"]


def match(query, criteria):
    scored = []
    for c in criteria:
        blob = " ".join([c["question"], c.get("how_to_measure", "")])
        scored.append((sim(query, blob), c))
    scored.sort(key=lambda x: -x[0])
    top = [(s, c) for s, c in scored if s >= 0.12][:3]
    if not top:
        top = scored[:1]
    return top


def stance(query, ids):
    if any(k in query for k in ["现金流为负", "连续为负", "见不到钱", "压库存"]) and "Q-cashflow-filter" in ids:
        return "负面"
    if any(k in query for k in ["讲不清", "看不懂", "不懂", "认知之外"]) and "Q-cognition-circle" in ids:
        return "中性回避"
    return "原则陈述" if ids else "不确定"


def answer(query, criteria):
    top = match(query, criteria)
    ids = [c["id"] for _, c in top]
    refs = []
    for _, c in top:
        for r in c.get("source_refs", []):
            if r not in refs:
                refs.append(r)
    return {
        "question": query,
        "stance": stance(query, ids),
        "criteria_ids": ids,
        "source_refs": refs[:3],
        "evidence_tier": "criteria_only",
        "is_inference": True,
        "pending": [
            "⛔ 未接本地语料，无法回查原文；以下为判据推演，非本人观点",
            "⛔ 引语为 18 字以内节选，完整原话不公开",
        ],
        "reasoning": [{"criterion": c["id"], "score": round(s, 4), "why": c["question"]} for s, c in top],
        "disclaimer": DISCLAIMER,
    }


def render(a):
    lines = [
        f"【结论】{a['stance']}（判据推演，非本人观点）",
        "【依据】" + "；".join(f"{r['criterion']}：{r['why']}" for r in a["reasoning"]),
        "【出处】" + ("；".join(a["source_refs"]) if a["source_refs"] else "无"),
        f"【证据等级】{a['evidence_tier']}（仅用冻结判据，未接语料）",
        "【待补充】" + " / ".join(a["pending"]),
        a["disclaimer"],
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="quange-judgment 规则版答题器")
    ap.add_argument("query")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--criteria", default=str(ROOT / "docs/criteria.json"))
    args = ap.parse_args()
    criteria = load(args.criteria)
    a = answer(args.query, criteria)
    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=2))
    else:
        print(render(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
