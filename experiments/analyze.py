# -*- coding: utf-8 -*-
"""实验02 深挖分析：工具名的可见性分层"""
import json, os, re, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(D, "data_mmd_raw.json"), encoding="utf-8"))
res = json.load(open(os.path.join(D, "data_mmd.json"), encoding="utf-8"))

OUT = []
def p(s=""):
    OUT.append(s)
    print(s)

p("=" * 72)
p("A. 核心统计")
p("=" * 72)
n = len(raw)
p("样本视频数: %d" % n)

# 重新解析（与爬虫一致的宽松规则）
TOOL_KEYWORDS = ["mme", "渲染", "软件", "插件", "材质", "tool", "工具", "特效", "shader"]
URL_RE = re.compile(r"https?://[^\s，。、）)\]}】]+")
LABEL_RE = re.compile(
    r"^\s*[【\[]?\s*([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff0-9_/]{0,11})\s*[】\]]?\s*"
    r"(?:[：:]+|\s{1,})\s*(.+)$")
SPLIT_RE = re.compile(r"[/／、,，;；|｜\s]+")

def label_is_tool(l):
    l = l.lower().replace(" ", "")
    return any(k in l for k in TOOL_KEYWORDS)

# 更严格：只保留"看起来像工具/作者名"的 token（英文名 或 短中文名/日文名）
def toolish(t):
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-\.]{1,23}", t):
        return True
    # 日文片假名/平假名 或 中文 2-6 字（作者名）
    if re.fullmatch(r"[\u3040-\u30ff\u4e00-\u9fff]{2,6}", t):
        return True
    return False

tool_videos = defaultdict(list)     # tool -> [idx]
per_video_tools = []
label_counter = Counter()
unparsed_with_toolword = []

for i, r in enumerate(raw):
    desc = r.get("desc", "") or ""
    found = set()
    has_label = False
    for line in desc.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        m = LABEL_RE.match(line)
        if not m:
            continue
        has_label = True
        lab, val = m.group(1).strip(), m.group(2).strip()
        label_counter[lab] += 1
        if label_is_tool(lab):
            val2 = URL_RE.sub(" ", val)
            for t in SPLIT_RE.split(val2):
                t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
                if 2 <= len(t) <= 24 and toolish(t):
                    found.add(t)
    per_video_tools.append(sorted(found))
    for t in found:
        tool_videos[t].append(i)
    # 有工具关键词但没解析出标签行 → 记录用于诊断
    if not has_label and any(k in desc.lower() for k in ["mme", "渲染", "插件"]):
        if len(unparsed_with_toolword) < 5:
            unparsed_with_toolword.append((r["bvid"], r["title"][:40], desc[:260]))

p("有标签行的视频: %d (%.1f%%)" % (sum(1 for t in per_video_tools if t), 0))
with_tools = sum(1 for t in per_video_tools if t)
p("解析出工具的视频: %d (%.1f%%)" % (with_tools, with_tools / n * 100))
p("不同工具 token 总数: %d" % len(tool_videos))
p("出现 >=2 次的工具: %d" % sum(1 for v in tool_videos.values() if len(v) >= 2))

p()
p("=" * 72)
p("B. 决定性指标：工具名的可见性分层")
p("=" * 72)

all_tools = set(tool_videos.keys())
in_any_title = set()
in_any_desc = set(all_tools)
for t, idxs in tool_videos.items():
    for i in idxs:
        if t.lower() in raw[i]["title"].lower():
            in_any_title.add(t)
            break

p("被提到的不同工具名         : %d" % len(all_tools))
p("其中出现在过任意标题里的   : %d" % len(in_any_title))
p("只出现在简介/借物表里的    : %d (%.1f%%)"
  % (len(all_tools) - len(in_any_title),
     (len(all_tools) - len(in_any_title)) / len(all_tools) * 100))
p()
p("→ 出现在标题里的那几个是: %s" % (sorted(in_any_title) if in_any_title else "（无）"))

p()
p("=" * 72)
p("C. 工具 × 播放量：长尾分层")
p("=" * 72)
rows = []
for t, idxs in tool_videos.items():
    vs = sorted(raw[i]["view"] for i in idxs)
    rows.append({
        "tool": t,
        "n": len(idxs),
        "median_view": vs[len(vs) // 2],
        "max_view": vs[-1],
        "min_view": vs[0],
    })
rows.sort(key=lambda r: (-r["n"], r["tool"]))

p("%-22s %5s %12s %12s %12s" % ("tool", "视频数", "中位播放", "最低播放", "最高播放"))
for r in rows[:35]:
    p("%-22s %5d %12d %12d %12d" % (r["tool"], r["n"], r["median_view"], r["min_view"], r["max_view"]))

p()
p("只在播放量 < 5万 的视频里出现的工具（真正的长尾）:")
lt = [r for r in rows if r["max_view"] < 50000 and r["n"] >= 2]
for r in lt:
    p("  %-22s n=%d  maxView=%d" % (r["tool"], r["n"], r["max_view"]))
if not lt:
    p("  （无）")

p()
p("=" * 72)
p("D. 借物表里最常出现的标签字段")
p("=" * 72)
for lab, c in label_counter.most_common(25):
    mark = "  ← 工具类" if label_is_tool(lab) else ""
    p("  %-18s %4d%s" % (lab, c, mark))

p()
p("=" * 72)
p("E. 「珍藏型」长尾：收藏/播放比最高的低播放视频")
p("=" * 72)
gems = res["hidden_gems_by_fav_ratio"]
for g in gems[:15]:
    p("  %-8s view=%-8d fav=%-7d fav/千播=%-7.1f  %s"
      % (g["bvid"], g["view"], g["favorite"], g["fav_per_1k"], g["title"][:38]))

p()
p("=" * 72)
p("F. 解析诊断：有工具关键词但没解析出标签的简介样本")
p("=" * 72)
for bv, ti, d in unparsed_with_toolword:
    p("  [%s] %s" % (bv, ti))
    p("    %s" % d.replace("\n", " | ")[:230])
    p()

p("=" * 72)
p("G. 分发渠道（工具从哪里下载）")
p("=" * 72)
for d, c in res["domains"][:20]:
    p("  %-34s %d" % (d, c))

open(os.path.join(D, "analysis.txt"), "w", encoding="utf-8").write("\n".join(OUT))
print("\n[saved analysis.txt]")
