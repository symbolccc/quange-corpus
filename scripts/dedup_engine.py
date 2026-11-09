"""跨平台去重引擎：规范化标题 + 时长(±3s) + 发布时间 三重指纹
覆盖源：YouTube(videos/streams/日期回填) / 抖音(主号+小号) / 快手(待采)
输出：corpus-index/master-fingerprints.jsonl + dedup-report.md
用途：任何后续下载/转写动作先查此指纹库，三元组命中已有条目 => 不再重复下载。"""
import json, os, re, unicodedata
from collections import defaultdict

BASE = r"C:\Users\11631\OneDrive\桌面\03_投资与命理\quange-corpus"
YT_V = os.path.join(BASE, "corpus", "youtube", "videos_titled.txt")
YT_D = os.path.join(BASE, "corpus", "youtube", "videos_dates.txt")
YT_S = os.path.join(BASE, "corpus", "youtube", "streams.txt")
DY_MAIN = r"D:\全哥\douyin\quange_main.jsonl"
DY_LUFEI = r"D:\全哥\douyin\lufei59627.jsonl"
KS = r"D:\全哥\kuaishou\kuaishou_unique.jsonl"  # 仅自营号且已剔除与抖音/YouTube重复
OUT_JSONL = os.path.join(BASE, "corpus-index", "master-fingerprints.jsonl")
OUT_MD = os.path.join(BASE, "corpus-index", "dedup-report.md")

PUNCT = re.compile(r"[\s\u3000]+|[!!\"#$%&()*+,，。.:：;；?<<?>《》【】\[\]{}「」|·—\-_/\\~～`^‘’“”]+")
EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]+")
TAGS = re.compile(r"#\S+")
NOISE = re.compile(r"(正在直播|直播回放|完整版?|合集|视频|抖音短视频|快手短视频|录屏\d*)")

def norm_title(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKC", str(t))
    t = TAGS.sub("", t)
    t = EMOJI.sub("", t)
    t = PUNCT.sub("", t.lower())
    return t

def ymd(ts_or_str):
    """统一化为 YYYYMMDD 或 ''"""
    if ts_or_str in (None, "", "NA", "ERR"):
        return ""
    s = str(ts_or_str)
    if re.match(r"^\d{8}$", s):
        return s
    try:
        v = int(float(s))
        import datetime
        if v > 10**11:  # ms
            v //= 1000
        return datetime.datetime.utcfromtimestamp(v + 8 * 3600).strftime("%Y%m%d")
    except Exception:
        return ""

items = []  # {platform, id, title, dur, dur_ms, date}

def add(platform, cid, title, dur, date="", dur_ms=None):
    nt = norm_title(title)
    if not nt and not dur:
        return
    items.append({"platform": platform, "id": str(cid), "title": (title or "")[:120],
                  "nt": nt, "dur": int(dur) if dur else 0, "date": ymd(date),
                  "dur_ms": int(dur_ms) if dur_ms else None})

# YouTube
if os.path.exists(YT_D):
    for line in open(YT_D, encoding="utf-8"):
        p = line.rstrip("\n").split("|", 3)
        if len(p) >= 3:
            add("youtube", p[0], p[3] if len(p) > 3 else "", p[2], p[1])
if os.path.exists(YT_S):
    for line in open(YT_S, encoding="utf-8"):
        p = line.rstrip("\n").split("|", 2)
        if len(p) >= 2:
            add("youtube_stream", p[0], p[2] if len(p) > 2 else "", p[1], "")
# 抖音
for path, plat in ((DY_MAIN, "douyin"), (DY_LUFEI, "douyin_lufei")):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            add(plat, d.get("aweme_id"), d.get("desc"), (d.get("duration_ms") or 0) // 1000, d.get("create_time"), d.get("duration_ms"))
# 快手
if os.path.exists(KS):
    for line in open(KS, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        add("kuaishou", d.get("photo_id"), d.get("caption"), (d.get("duration_ms") or 0) // 1000, d.get("timestamp"), d.get("duration_ms"))

# 聚类 v2：
#  A) 毫秒级时长精确相同 => 同一视频（抖音/快手 duration_ms 精度极高，最强指纹）
#  B) 规范化标题相同 + 时长±3s + (双日期须同日) => 同一内容（用于 YouTube 秒级时长）
#  C) 纯标签空标题项：仅靠 A 聚类，绝不丢
from difflib import SequenceMatcher
parent = list(range(len(items)))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

# A) 毫秒时长
by_ms = defaultdict(list)
for i, it in enumerate(items):
    raw_ms = it.get("dur_ms")
    if raw_ms:
        by_ms[raw_ms].append(i)
for idxs in by_ms.values():
    for j in idxs[1:]:
        union(idxs[0], j)

# B) 标题+秒时长+日期
by_nt = defaultdict(list)
for i, it in enumerate(items):
    if it["nt"]:
        by_nt[it["nt"]].append(i)
for nt, idxs in by_nt.items():
    idxs2 = sorted(idxs, key=lambda i: items[i]["dur"])
    for a, b in zip(idxs2, idxs2[1:]):
        ia, ib = items[a], items[b]
        if abs(ia["dur"] - ib["dur"]) <= 3 or not ia["dur"] or not ib["dur"]:
            if ia["date"] and ib["date"] and ia["date"] != ib["date"]:
                continue
            union(a, b)

groups = defaultdict(list)
for i in range(len(items)):
    groups[find(i)].append(items[i])
clusters = []
for _, c in groups.items():
    plats = sorted({x["platform"] for x in c})
    t = "unique" if len(c) == 1 else ("cross" if len(plats) > 1 else "same_platform_dup")
    clusters.append({"type": t, "title": c[0]["title"], "members": c})

cross = [c for c in clusters if c["type"] == "cross"]
dup_same = [c for c in clusters if c["type"] == "same_platform_dup"]
uniq = [c for c in clusters if c["type"] == "unique"]

os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
with open(OUT_JSONL, "w", encoding="utf-8") as f:
    for i, c in enumerate(clusters):
        fp = {"cluster_id": i, "type": c["type"], "title": c["title"],
              "members": [{"platform": m["platform"], "id": m["id"], "dur": m["dur"],
                           "date": m["date"]} for m in c["members"]]}
        f.write(json.dumps(fp, ensure_ascii=False) + "\n")

by_plat = defaultdict(int)
for it in items:
    by_plat[it["platform"]] += 1

lines = ["# 跨平台去重报告", "",
         "- 总条目: %d ｜ 唯一内容簇: %d ｜ 跨平台重复簇: %d ｜ 同平台重复簇: %d" % (
             len(items), len(uniq), len(cross), len(dup_same)),
         "- 各平台条目: " + ", ".join("%s=%d" % kv for kv in sorted(by_plat.items())),
         "- 判定: 规范化标题一致 + 时长±3s + 双日期时须同日；命中即视为同一内容，不重复下载", ""]
if cross:
    lines.append("## 跨平台重复（保留优先级: youtube_stream > youtube > douyin > douyin_lufei > kuaishou）")
    lines.append("")
    lines.append("| 标题 | 时长(s) | 命中平台 | 日期 |")
    lines.append("|---|---|---|---|")
    for c in sorted(cross, key=lambda x: -len(x["members"]))[:120]:
        m = c["members"]
        lines.append("| %s | %d | %s | %s |" % (
            m[0]["title"][:40], m[0]["dur"],
            " + ".join(sorted({x["platform"] for x in m})),
            " / ".join(sorted({x["date"] for x in m if x["date"]})) or "-"))
    lines.append("")
with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("items=%d uniq=%d cross=%d dup_same=%d" % (len(items), len(uniq), len(cross), len(dup_same)))
print("report ->", OUT_MD)
