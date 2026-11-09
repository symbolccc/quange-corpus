#!/usr/bin/env python3
"""本地语料检索（零依赖）。

用法:
    python scripts/quange_search.py "现金流" --scope all --limit 20
    python scripts/quange_search.py "躺平" --scope xueqiu --context 1
    python scripts/quange_search.py "仓位" --scope transcripts --transcripts "D:/全哥/transcripts"

每条命中都带信源标签与文件路径，便于回原文核对。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSCRIPTS = Path("D:/全哥/transcripts")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def read_lines(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        print(f"[警告] 读不到 {path}: {e}", file=sys.stderr)
        return []


def build_records(scope, transcripts_dir):
    """返回 (信源标签, 显示路径, [文本行]) 列表。"""
    out = []
    if scope in ("xueqiu", "all"):
        d = ROOT / "corpus/xueqiu/articles_text"
        for p in sorted(d.glob("*.txt")):
            out.append(("雪球纯文本", p, read_lines(p)))
    if scope in ("transcripts", "all"):
        if transcripts_dir.is_dir():
            for p in sorted(transcripts_dir.glob("*.txt")):
                out.append(("直播转写(ASR)", p, read_lines(p)))
        else:
            print(f"[警告] 转写目录不存在，已跳过: {transcripts_dir}", file=sys.stderr)
    if scope in ("criteria", "all"):
        p = ROOT / "criteria/quange-criteria.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[警告] 判据读取失败: {e}", file=sys.stderr)
        else:
            lines = []
            for c in data.get("criteria", []):
                lines.append(f"{c.get('id')} | {c.get('question')} | {c.get('provenance')}")
                for q in c.get("evidence_quote", []):
                    lines.append(f"  原话: {q}")
                for r in c.get("source_refs", []):
                    lines.append(f"  出处: {r}")
            out.append(("判据quange-criteria.json", p, lines))
    return out


def main():
    ap = argparse.ArgumentParser(description="全哥语料本地检索")
    ap.add_argument("query", help="关键词（子串匹配）")
    ap.add_argument("--scope", choices=["all", "xueqiu", "transcripts", "criteria"], default="all")
    ap.add_argument("--limit", type=int, default=20, help="最多输出命中数")
    ap.add_argument("--context", type=int, default=0, help="命中行前后各显示几行")
    ap.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS), help="直播转写目录")
    ap.add_argument("--max-chars", type=int, default=220, help="单行截断长度")
    args = ap.parse_args()

    q = args.query.lower()
    records = build_records(args.scope, Path(args.transcripts))
    hits = 0
    total_files = len(records)
    for label, path, lines in records:
        matched_idx = [i for i, line in enumerate(lines) if q in line.lower()]
        if not matched_idx:
            continue
        try:
            shown = str(path.relative_to(ROOT))
        except ValueError:
            shown = str(path)
        for i in matched_idx[: max(0, args.limit - hits)]:
            hits += 1
            print(f"\n[{label}] {shown}:{i + 1}")
            lo, hi = max(0, i - args.context), min(len(lines), i + args.context + 1)
            for j in range(lo, hi):
                mark = ">>" if j == i else "  "
                text = lines[j].strip()
                if len(text) > args.max_chars:
                    text = text[: args.max_chars] + "…"
                print(f"  {mark} {j + 1}: {text}")
        if hits >= args.limit:
            break
    print(f"\n—— 共 {total_files} 个文件，输出 {hits} 条命中（上限 {args.limit}）；关键词: {args.query}")
    if hits == 0:
        print("⛔ 无命中：请换关键词，或确认 --scope / --transcripts 路径。")


if __name__ == "__main__":
    main()
