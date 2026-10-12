# -*- coding: utf-8 -*-
"""
实验 03（补测）：评论区抽取 —— 简介之外，还有多少工具藏在评论区？

背景：实验02 只有 12.6% 的视频能从简介解析出工具。诊断发现部分作者把
      「配布地址 / 插件包」放在置顶评论（简介有 250 字上限）。

方法：
  Phase 1  重爬相关推荐图，这次保存 aid（评论接口需要 oid=aid）
  Phase 2  对抽样视频抓评论第 1 页（含 UP 主置顶评论）
  Phase 3  对比「简介解析出的工具」vs「评论解析出的工具」，
           重点测：评论独有工具数、解析率提升幅度

接口：
  /x/web-interface/archive/related   相关推荐（含 aid）
  /x/v2/reply?type=1&oid=<aid>&sort=2&ps=20&pn=1   评论（可用，无需登录）
"""
import urllib.request, urllib.error
import json, time, re, os, sys, random
from collections import Counter, defaultdict

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}
D = os.path.dirname(os.path.abspath(__file__))
TARGET_VIDEOS = int(os.environ.get("TARGET_VIDEOS", "400"))
COMMENT_SAMPLE = int(os.environ.get("COMMENT_SAMPLE", "180"))
SLEEP = float(os.environ.get("SLEEP", "0.8"))

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


# ---------------- 工具抽取 ----------------

URL_RE = re.compile(r"https?://[^\s，。、）)\]}】\"'<]+")
NAME_TYPE_AUTHOR = re.compile(
    r"([A-Za-z][A-Za-z0-9_\-\.]{2,29})\s*[（(]([^）)]{1,14})[）)]\s*[：:]\s*([^|｜\n]+)")
FIELD_RE = re.compile(
    r"^[【\[]?\s*(MME|mme|Shader|shader|渲染|材质|特效|Effect|effect|PostEffect|"
    r"软件|插件|Tool|工具)\s*[】\]]?\s*[：:\s]\s*(.+)$")
SPLIT = re.compile(r"[/／、,，;；|｜\s]+")
ENG = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{2,29}$")

# 明显不是工具的英文词
STOP = set("""the and for with you are not but all can how what this that from your
mmd pmx vmd vpv vmd pmd blender miku mikumikudance dance video music model motion
camera stage bgm bilibili com www http https bowlroll pan baidu github
new old ver version test demo final fix fixed upd update
please thanks thank good nice very more less than about
""".split())


def is_tool_token(t):
    if not ENG.match(t):
        return False
    if t.lower() in STOP:
        return False
    if len(t) < 3:
        return False
    # 至少含一个字母，且不是纯版本号
    if re.fullmatch(r"[vV]?\d+(\.\d+)*", t):
        return False
    return True


def extract_tools(text):
    """从一段文本（简介或评论）里抽工具名"""
    if not text:
        return set(), []
    tools = set()
    urls = URL_RE.findall(text)
    # 1) 效果名（类型）：作者
    for m in NAME_TYPE_AUTHOR.finditer(text):
        name = m.group(1)
        if is_tool_token(name):
            tools.add(name)
    # 2) MME 字段行
    for line in text.splitlines():
        line = line.strip()
        m = FIELD_RE.match(line)
        if not m:
            continue
        val = URL_RE.sub(" ", m.group(2))
        for t in SPLIT.split(val):
            t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
            if is_tool_token(t):
                tools.add(t)
    return tools, urls


# ---------------- Phase 1：重爬（存 aid） ----------------

def crawl():
    cache = os.path.join(D, "data_aid.json")
    if os.path.exists(cache):
        try:
            vids = json.load(open(cache, encoding="utf-8"))
            if len(vids) >= 300:
                print("reuse cache: %d videos" % len(vids))
                return vids
        except Exception:
            pass

    videos = {}
    expanded = set()
    queue = list(SEEDS)
    calls = 0
    while queue and len(videos) < TARGET_VIDEOS:
        bv = queue.pop(0)
        if bv in expanded:
            continue
        if bv not in videos:
            d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bv)
            calls += 1; time.sleep(SLEEP)
            if d and d.get("code") == 0:
                v = d["data"]
                videos[bv] = {
                    "bvid": bv, "aid": v.get("aid"),
                    "title": v.get("title", "") or "", "desc": v.get("desc", "") or "",
                    "view": (v.get("stat") or {}).get("view", 0) or 0,
                    "favorite": (v.get("stat") or {}).get("favorite", 0) or 0,
                    "pubdate": v.get("pubdate", 0) or 0,
                }
        d = fetch("https://api.bilibili.com/x/web-interface/archive/related?bvid=" + bv)
        calls += 1; time.sleep(SLEEP)
        expanded.add(bv)
        if d and d.get("code") == 0:
            for v in d.get("data", []):
                rb = v.get("bvid")
                if not rb:
                    continue
                if rb not in videos:
                    videos[rb] = {
                        "bvid": rb, "aid": v.get("aid"),
                        "title": v.get("title", "") or "", "desc": v.get("desc", "") or "",
                        "view": (v.get("stat") or {}).get("view", 0) or 0,
                        "favorite": (v.get("stat") or {}).get("favorite", 0) or 0,
                        "pubdate": v.get("pubdate", 0) or 0,
                    }
                if rb not in expanded:
                    queue.append(rb)
        if calls % 20 == 0:
            print("  crawl videos=%d calls=%d" % (len(videos), calls))
    vids = list(videos.values())
    json.dump(vids, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("crawl done: %d videos, %d calls" % (len(vids), calls))
    return vids


# ---------------- Phase 2：抓评论 ----------------

def pick_sample(vids):
    """优先挑「简介里有工具关键词但解析不出工具」的视频，其余按顺序补足"""
    priority, rest = [], []
    for v in vids:
        d = v.get("desc", "")
        dt, _ = extract_tools(d)
        has_kw = any(k in d for k in ["MME", "mme", "渲染", "插件", "Shader", "材质", "配布"])
        if has_kw and not dt:
            priority.append(v)
        else:
            rest.append(v)
    random.seed(42)
    random.shuffle(rest)
    return (priority + rest)[:COMMENT_SAMPLE], len(priority)


def fetch_comments(v):
    aid = v.get("aid")
    if not aid:
        return None
    url = ("https://api.bilibili.com/x/v2/reply?type=1&oid=%d&sort=2&ps=20&pn=1" % aid)
    d = fetch(url, retries=2)
    time.sleep(SLEEP)
    if not d or d.get("code") != 0:
        return {"_err": (d or {}).get("code")}
    data = d.get("data") or {}
    msgs = []
    # UP 主置顶
    top = ((data.get("upper") or {}).get("top")) or data.get("top")
    if top and (top.get("content") or {}).get("message"):
        msgs.append(("UP置顶", top["content"]["message"]))
    # 普通评论
    for r in (data.get("replies") or []):
        m = (r.get("content") or {}).get("message")
        if m:
            msgs.append(("评论", m))
    return {"total": (data.get("page") or {}).get("count", 0), "msgs": msgs}


def main():
    vids = crawl()
    by_bv = {v["bvid"]: v for v in vids}

    # 简介基线
    for v in vids:
        dt, du = extract_tools(v.get("desc", ""))
        v["_desc_tools"] = sorted(dt)
        v["_desc_urls"] = du

    desc_ok = [v for v in vids if v["_desc_tools"]]
    print("\n[baseline] 简介可解析出工具: %d/%d = %.1f%%"
          % (len(desc_ok), len(vids), len(desc_ok) / len(vids) * 100))

    sample, n_prio = pick_sample(vids)
    print("[sample] 抓评论 %d 个视频（其中 %d 个是「简介有工具词但解析不出」的优先组）"
          % (len(sample), n_prio))

    results = []
    errs = 0
    for i, v in enumerate(sample, 1):
        c = fetch_comments(v)
        if not c or "_err" in (c or {}):
            errs += 1
            results.append({"bvid": v["bvid"], "ok": False})
        else:
            ct, cu = set(), []
            for kind, msg in c["msgs"]:
                t, u = extract_tools(msg)
                ct |= t
                cu.extend(u)
            v["_cmt_tools"] = sorted(ct)
            v["_cmt_urls"] = cu
            v["_cmt_total"] = c["total"]
            v["_cmt_n"] = len(c["msgs"])
            results.append({"bvid": v["bvid"], "ok": True})
        if i % 20 == 0:
            print("  comments %d/%d (err=%d)" % (i, len(sample), errs))

    ok = [v for v in sample if v.get("_cmt_tools") is not None]

    # ---- 对比 ----
    desc_only_hit = [v for v in ok if v["_desc_tools"] and not v["_cmt_tools"]]
    cmt_only_hit = [v for v in ok if v["_cmt_tools"] and not v["_desc_tools"]]
    both = [v for v in ok if v["_desc_tools"] and v["_cmt_tools"]]
    neither = [v for v in ok if not v["_desc_tools"] and not v["_cmt_tools"]]

    union = [v for v in ok if v["_desc_tools"] or v["_cmt_tools"]]
    inter = set(desc_only_hit) & set(cmt_only_hit)

    base_rate = len(desc_ok) / len(vids) * 100
    sample_desc_rate = sum(1 for v in ok if v["_desc_tools"]) / len(ok) * 100
    union_rate = len(union) / len(ok) * 100

    # 评论独有工具
    desc_all = set()
    for v in vids:
        desc_all |= set(v["_desc_tools"])
    cmt_all = set()
    for v in ok:
        cmt_all |= set(v["_cmt_tools"])
    cmt_exclusive = cmt_all - desc_all

    # 评论里出现、且带 URL 的工具（= 有配布地址的）
    tool_with_url = defaultdict(int)
    for v in ok:
        for u in v.get("_cmt_urls", []):
            m = re.match(r"https?://([^/]+)", u)
            if m:
                tool_with_url[m.group(1).lower()] += 1

    # 评论里 URL 的域名
    cmt_domains = Counter()
    for v in ok:
        for u in v.get("_cmt_urls", []):
            m = re.match(r"https?://([^/]+)", u)
            if m:
                cmt_domains[m.group(1).lower()] += 1

    out = {
        "n_videos": len(vids),
        "comment_sample": len(sample),
        "comment_fetch_errors": errs,
        "baseline_desc_parse_rate": round(base_rate, 2),
        "sample_desc_parse_rate": round(sample_desc_rate, 2),
        "union_desc_or_comment_rate": round(union_rate, 2),
        "lift_pp": round(union_rate - sample_desc_rate, 2),
        "counts": {
            "desc_only": len(desc_only_hit),
            "comment_only": len(cmt_only_hit),
            "both": len(both),
            "neither": len(neither),
        },
        "distinct_tools_desc": len(desc_all),
        "distinct_tools_comment": len(cmt_all),
        "comment_exclusive_tools": sorted(cmt_exclusive),
        "comment_exclusive_count": len(cmt_exclusive),
        "comment_domains": cmt_domains.most_common(25),
        "examples": [{
            "bvid": v["bvid"], "title": v["title"][:60], "view": v["view"],
            "desc_tools": v["_desc_tools"][:8], "cmt_tools": v["_cmt_tools"][:8],
            "cmt_total": v.get("_cmt_total", 0),
        } for v in (cmt_only_hit + both)[:25]],
    }
    json.dump(out, open(os.path.join(D, "data_comments.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump([{k: v for k, v in x.items() if not k.startswith("_")} for x in vids],
              open(os.path.join(D, "data_aid_raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n" + "=" * 70)
    print("结果")
    print("=" * 70)
    print("全样本 %d 视频" % len(vids))
    print("简介解析率（全样本）      : %.1f%%" % base_rate)
    print("简介解析率（评论抽样内）  : %.1f%%" % sample_desc_rate)
    print("简介+评论 合并解析率      : %.1f%%" % union_rate)
    print("→ 提升                    : +%.1f 个百分点" % (union_rate - sample_desc_rate))
    print()
    print("抽样 %d 个中:" % len(ok))
    print("  只有简介能解析出工具 : %d" % len(desc_only_hit))
    print("  只有评论能解析出工具 : %d   ← 关键" % len(cmt_only_hit))
    print("  两边都有             : %d" % len(both))
    print("  两边都没有           : %d" % len(neither))
    print()
    print("不同工具名: 简介 %d 个 / 评论 %d 个" % (len(desc_all), len(cmt_all)))
    print("评论独有工具 %d 个:" % len(cmt_exclusive))
    for t in sorted(cmt_exclusive)[:40]:
        print("   ", t)
    print()
    print("评论里出现的分发域名 top15:")
    for d_, c_ in cmt_domains.most_common(15):
        print("  %-32s %d" % (d_, c_))
    print("\nsaved: data_comments.json")


if __name__ == "__main__":
    main()
