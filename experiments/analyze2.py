# -*- coding: utf-8 -*-
"""实验02 v3：修正提取规则，分离「工具名 / 作者名」，并检验可见性结论"""
import json, os, re
from collections import Counter, defaultdict

D = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(D, "data_mmd_raw.json"), encoding="utf-8"))

OUT = []
def p(s=""):
    OUT.append(s); print(s)

# 真实借物表格式（从样本里学到的）：
#   ikClut_RC（滤镜）：RedialC/iKeno | msUnsharp（锐化效果）：ましまし | MotionBlur3（运动模糊）：そぼろ
#   MME：P.I.P/HAToon2/ExcellentShadow/化身バレッタ/角砂糖/金针P
#   MME びーと/less./Caeru/鍵束/P.I.P
NAME_TYPE_AUTHOR = re.compile(
    r"([A-Za-z][A-Za-z0-9_\-\.]{2,29})\s*[（(]([^）)]{1,14})[）)]\s*[：:]\s*([^|｜\n]+)")
# 纯工具名 token：英文/数字/下划线/点/连字符，长度>=3，至少含一个字母
ENG_TOOL = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{2,29}$")
URL_RE = re.compile(r"https?://[^\s，。、）)\]}】]+")
SPLIT = re.compile(r"[/／、,，;；|｜\s]+")

# 借物表字段：中英日标签 + 分隔符
FIELD = re.compile(
    r"^[【\[]?\s*(MME|mme|Shader|shader|渲染|材质|特效|Effect|effect|PostEffect|软件|插件|Tool|工具)"
    r"\s*[】\]]?\s*[：:\s]\s*(.+)$")

tool_mention = defaultdict(list)   # 工具名 -> [video idx]
author_mention = defaultdict(list)
pairs = []                         # (tool, type, author, view, bvid)

for i, r in enumerate(raw):
    desc = r.get("desc", "") or ""
    # 1) 名称（类型）：作者
    for m in NAME_TYPE_AUTHOR.finditer(desc):
        name, typ, author = m.group(1), m.group(2), m.group(3).strip()
        if name.lower() in ("http", "https", "www"):
            continue
        pairs.append((name, typ, author, r["view"], r["bvid"]))
        tool_mention[name].append(i)
        for a in SPLIT.split(author):
            a = a.strip(" 　.。/、")
            if 2 <= len(a) <= 20:
                author_mention[a].append(i)
    # 2) MME 字段行里的裸工具名
    for line in desc.splitlines():
        line = line.strip()
        m = FIELD.match(line)
        if not m:
            continue
        val = URL_RE.sub(" ", m.group(2))
        for t in SPLIT.split(val):
            t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
            if ENG_TOOL.match(t) and 3 <= len(t) <= 29:
                tool_mention[t].append(i)

n = len(raw)

p("=" * 74)
p("H. 修正提取：工具名（英文效果名） vs 作者名")
p("=" * 74)
p("样本: %d 视频" % n)
p("提取到「名称（类型）：作者」结构的条目: %d" % len(pairs))
p("不同工具名(英文效果名)总数: %d" % len(tool_mention))
p("不同作者名总数: %d" % len(author_mention))

p()
p("--- 工具名 top 25（按被引用视频数）---")
p("%-26s %5s %10s %10s %10s" % ("工具名", "视频数", "中位播放", "最低", "最高"))
rows = []
for t, idxs in tool_mention.items():
    vs = sorted(raw[i]["view"] for i in idxs)
    rows.append((t, len(idxs), vs[len(vs)//2], vs[0], vs[-1]))
rows.sort(key=lambda x: (-x[1], x[0]))
for t, c, med, lo, hi in rows[:25]:
    p("%-26s %5d %10d %10d %10d" % (t, c, med, lo, hi))

p()
p("--- 「名称（类型）：作者」样例（证明借物表是结构化的）---")
seen = set()
shown = 0
for name, typ, author, view, bv in pairs:
    if name in seen:
        continue
    seen.add(name)
    p("  %-22s 类型=%-10s 作者=%-18s view=%-8d %s" % (name, typ, author[:18], view, bv))
    shown += 1
    if shown >= 20:
        break

p()
p("=" * 74)
p("I. 可见性检验（修正后）：工具名是否出现在标题里")
p("=" * 74)
in_title = []
for t, idxs in tool_mention.items():
    for i in idxs:
        if t.lower() in raw[i]["title"].lower():
            in_title.append(t); break
p("不同工具名总数        : %d" % len(tool_mention))
p("出现在过标题里的      : %d" % len(in_title))
p("只出现在简介/借物表里 : %d (%.1f%%)"
  % (len(tool_mention) - len(in_title),
     (len(tool_mention) - len(in_title)) / len(tool_mention) * 100))
if in_title:
    p("出现在标题里的是: %s" % sorted(in_title))

p()
p("=" * 74)
p("J. 长尾工具：只在低播放视频里出现")
p("=" * 74)
p("只在 maxView < 3万 的视频里出现的工具:")
lt = [(t, c, med, lo, hi) for t, c, med, lo, hi in rows if hi < 30000]
for t, c, med, lo, hi in lt:
    p("  %-26s n=%-3d 中位=%-7d 最高=%d" % (t, c, med, hi))
if not lt:
    p("  （无）")

p()
p("只在 maxView < 10万 的视频里出现的工具（前 20 个）:")
lt2 = [(t, c, med, lo, hi) for t, c, med, lo, hi in rows if hi < 100000]
for t, c, med, lo, hi in lt2[:20]:
    p("  %-26s n=%-3d 中位=%-7d 最高=%d" % (t, c, med, hi))

p()
p("=" * 74)
p("K. 借物表字段的三种格式（供后续解析器设计）")
p("=" * 74)
p("""格式1  效果名（效果类型）：作者
       ikClut_RC（滤镜）：RedialC/iKeno
       msUnsharp（锐化效果）：ましまし
       信息量最大：工具名 + 用途 + 作者，三者齐全

格式2  MME：作者名/作者名/作者名
       MME：P.I.P/HAToon2/ExcellentShadow/化身バレッタ
       只给名字，工具与作者混在一起

格式3  效果名 作者（空格分隔，无冒号）
       MME びーと/less./Caeru/鍵束/P.I.P
       最弱，切分靠猜""")

open(os.path.join(D, "analysis2.txt"), "w", encoding="utf-8").write("\n".join(OUT))
print("\n[saved analysis2.txt]")
