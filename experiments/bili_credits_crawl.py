# -*- coding: utf-8 -*-
"""
实验 02（v2）：从 B 站作品简介的「借物表」反向提取工具清单

修复：
  - v1 的 BFS 把种子全部跳过，related 一次没调 → 用 expanded 集合单独跟踪
  - v1 的借物表解析要求「标签:内容」，漏掉「MME 内容」「【MME】内容」等格式
"""
import urllib.request
import json
import time
import re
import os
import sys
from collections import Counter, defaultdict

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = int(os.environ.get("TARGET", "400"))
SLEEP = float(os.environ.get("SLEEP", "1.0"))

SEEDS = [
    "BV1tGW4zYEye", "BV1qVqmYFENA", "BV15deJ6KEET", "BV1cJ396JEAN",
    "BV15Badz2E5s", "BV1PWW8eVEGM", "BV1iY4y1N78J", "BV1U3411g7ka",
    "BV1kCTu6JEvw", "BV1qLbe6wEjF", "BV1eSp4zVES5", "BV1op4y1u7La",
    "BV15c411r7BF", "BV1ADRKYvE9M", "BV1jG4y1K7bP",
]


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries - 1:
                print("  ! fail %s (%s)" % (url[:70], e), file=sys.stderr)
                return None
            time.sleep(2 + i * 2)
    return None


# ---------------- 借物表解析 ----------------

TOOL_KEYWORDS = ["mme", "渲染", "软件", "插件", "材质", "tool", "工具", "特效", "shader"]

NOISE = set("""
无 暂无 自制 原创 转载 侵删 详见 见 结尾 最后 如下 以下 上面 下面 全部 其他
模型编辑 版权所属 动作转换 视频制作 后期 剪辑 软件下载 感谢 感谢观看 禁止 二配
大佬 老师 借物表 借物 参考 视频 教程 新人 新手 注意 说明
""".split())

URL_RE = re.compile(r"https?://[^\s，。、）)\]}】]+")
# 标签行：标签[：:或空白]内容   标签可带【】[]
LABEL_RE = re.compile(
    r"^\s*[【\[]?\s*([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff0-9_/]{0,11})\s*[】\]]?\s*"
    r"(?:[：:]+|\s{1,})\s*(.+)$"
)
SPLIT_RE = re.compile(r"[/／、,，;；|｜\s]+")
# 纯英数工具名结构（如 AutoLuminous、SvSSAO、ray-cast、patoon、b toon）
TOOLISH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{1,23}$")


def label_is_tool(label):
    l = label.lower().replace(" ", "")
    return any(k in l for k in TOOL_KEYWORDS)


def clean_tokens(value):
    """把字段值切成工具名 token"""
    value = URL_RE.sub(" ", value)
    out = []
    for t in SPLIT_RE.split(value):
        t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
        if not t or len(t) < 2 or len(t) > 26:
            continue
        tl = t.lower()
        if t in NOISE or tl in NOISE:
            continue
        if t.startswith("http") or t.startswith("@"):
            continue
        if re.fullmatch(r"[\d\W]+", t):
            continue
        # 中文短语超过 6 字多半是句子不是工具名
        cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
        if cjk >= 7:
            continue
        out.append(t)
    return out


def parse_credits(desc):
    """返回 (tool_fields, all_labeled_fields, urls)"""
    tool_fields = []
    all_fields = []
    urls = URL_RE.findall(desc or "")
    if not desc:
        return tool_fields, all_fields, urls
    for line in desc.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue
        m = LABEL_RE.match(line)
        if not m:
            continue
        label, value = m.group(1).strip(), m.group(2).strip()
        if label_is_tool(label):
            toks = clean_tokens(value)
            if toks:
                tool_fields.append((label, toks))
        all_fields.append(label)
    return tool_fields, all_fields, urls


# ---------------- 抓取 ----------------

def rec_from_view(v, bvid, src):
    st = v.get("stat", {}) or {}
    ow = v.get("owner", {}) or {}
    return {
        "bvid": bvid,
        "title": v.get("title", "") or "",
        "desc": v.get("desc", "") or "",
        "view": st.get("view", 0) or 0,
        "like": st.get("like", 0) or 0,
        "favorite": st.get("favorite", 0) or 0,
        "coin": st.get("coin", 0) or 0,
        "reply": st.get("reply", 0) or 0,
        "pubdate": v.get("pubdate", 0) or 0,
        "duration": v.get("duration", 0) or 0,
        "tname": v.get("tname", "") or "",
        "up": ow.get("name", "") or "",
        "up_mid": ow.get("mid", 0) or 0,
        "source": src,
    }


def main():
    videos = {}
    expanded = set()
    queue = list(SEEDS)
    calls = 0

    while queue and len(videos) < TARGET:
        bv = queue.pop(0)
        if bv in expanded:
            continue
        # 没有详情就先取详情
        if bv not in videos:
            d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bv)
            calls += 1
            time.sleep(SLEEP)
            if d and d.get("code") == 0:
                videos[bv] = rec_from_view(d["data"], bv, "seed" if calls <= len(SEEDS) else "view")
        # 再取 related 扩展
        d = fetch("https://api.bilibili.com/x/web-interface/archive/related?bvid=" + bv)
        calls += 1
        time.sleep(SLEEP)
        expanded.add(bv)
        if d and d.get("code") == 0:
            for v in d.get("data", []):
                rb = v.get("bvid")
                if not rb:
                    continue
                if rb not in videos:
                    videos[rb] = rec_from_view(v, rb, "related")
                if rb not in expanded:
                    queue.append(rb)
        if calls % 20 == 0:
            print("  ... videos=%d calls=%d queue=%d" % (len(videos), calls, len(queue)))

    n = len(videos)
    print("crawl done: %d videos, %d calls, %d expanded" % (n, calls, len(expanded)))

    # ---------- 解析 ----------
    for r in videos.values():
        tf, af, urls = parse_credits(r["desc"])
        r["_toolfields"] = tf
        r["_labels"] = af
        r["_urls"] = urls
        tools = []
        for _, toks in tf:
            tools.extend(toks)
        r["_tools"] = sorted(set(tools))

    has_credits = [r for r in videos.values() if r["_labels"]]
    has_tool = [r for r in videos.values() if r["_tools"]]
    has_url = [r for r in videos.values() if r["_urls"]]

    views = sorted(r["view"] for r in videos.values())

    def q(p):
        return views[min(len(views) - 1, int(len(views) * p))] if views else 0

    buckets = [
        ("< 1千", lambda v: v < 1000),
        ("1千-1万", lambda v: 1000 <= v < 10000),
        ("1万-10万", lambda v: 10000 <= v < 100000),
        ("10万-100万", lambda v: 100000 <= v < 1000000),
        (">=100万", lambda v: v >= 1000000),
    ]
    view_dist = [{"bucket": nm, "count": sum(1 for v in views if f(v)),
                  "share": round(sum(1 for v in views if f(v)) / len(views), 4)}
                 for nm, f in buckets] if views else []

    # 只在"借物表"视频里统计工具
    tool_videos = defaultdict(list)
    for r in has_tool:
        for t in r["_tools"]:
            tool_videos[t].append(r["bvid"])

    tool_rows = []
    for t, bvs in tool_videos.items():
        if len(bvs) < 2:
            continue
        in_title = sum(1 for bv in bvs if t.lower() in videos[bv]["title"].lower())
        vs = sorted(videos[bv]["view"] for bv in bvs)
        tool_rows.append({
            "tool": t,
            "n_videos": len(bvs),
            "in_title_count": in_title,
            "only_in_desc": len(bvs) - in_title,
            "median_view": vs[len(vs) // 2],
            "max_view": vs[-1],
            "min_view": vs[0],
        })
    tool_rows.sort(key=lambda r: (-r["n_videos"], r["tool"]))

    domain_counter = Counter()
    for r in has_url:
        for u in r["_urls"]:
            m = re.match(r"https?://([^/]+)", u)
            if m:
                domain_counter[m.group(1).lower()] += 1

    # "珍藏型"长尾：收藏/播放比高，且播放量不高
    def fav_ratio(r):
        return (r["favorite"] / r["view"]) if r["view"] > 0 else 0

    gems = sorted([r for r in videos.values() if r["view"] >= 300],
                  key=lambda r: -fav_ratio(r))[:30]

    # 长尾工具：只出现在中位播放 < 2万的视频里的工具
    longtail_tools = [t for t in tool_rows
                      if t["median_view"] < 20000 and t["n_videos"] >= 2]

    summary = {
        "total_videos": n,
        "api_calls": calls,
        "has_credits_share": round(len(has_credits) / n, 4) if n else 0,
        "has_tool_field_share": round(len(has_tool) / n, 4) if n else 0,
        "has_url_share": round(len(has_url) / n, 4) if n else 0,
        "view_min": views[0] if views else 0,
        "view_p25": q(0.25), "view_median": q(0.5), "view_p75": q(0.75),
        "view_max": views[-1] if views else 0,
        "distinct_tool_tokens": len(tool_videos),
        "tools_in_ge2_videos": len(tool_rows),
        "longtail_tools_ge2": len(longtail_tools),
    }

    result = {
        "summary": summary,
        "view_distribution": view_dist,
        "tools": tool_rows,
        "longtail_tools": longtail_tools,
        "domains": domain_counter.most_common(40),
        "hidden_gems_by_fav_ratio": [{
            "bvid": r["bvid"], "title": r["title"][:70], "view": r["view"],
            "favorite": r["favorite"], "fav_per_1k": round(fav_ratio(r) * 1000, 1),
            "n_tools": len(r["_tools"]), "tools": r["_tools"][:8],
        } for r in gems],
    }
    with open(os.path.join(OUT_DIR, "data_mmd.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "data_mmd_raw.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if not k.startswith("_")}
                   for r in videos.values()], f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n--- 播放量分布 ---")
    for b in view_dist:
        print("  %-10s %5d  %5.1f%%" % (b["bucket"], b["count"], b["share"] * 100))
    print("\n--- 工具名：在标题里 vs 只在简介里 ---")
    print("  %-24s %6s %9s %10s %10s" % ("tool", "视频数", "标题里有", "只在简介", "中位播放"))
    for t in tool_rows[:30]:
        print("  %-24s %6d %9d %10d %10d"
              % (t["tool"], t["n_videos"], t["in_title_count"], t["only_in_desc"], t["median_view"]))
    print("\n--- 工具分发域名 ---")
    for d, c in domain_counter.most_common(15):
        print("  %-34s %d" % (d, c))
    print("\nsaved: data_mmd.json / data_mmd_raw.json")


if __name__ == "__main__":
    main()
