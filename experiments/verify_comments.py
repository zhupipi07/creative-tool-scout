# -*- coding: utf-8 -*-
"""
实验03 完整性核查
疑问：评论独有工具 = 0，是真的没有，还是我的评论提取器太严（评论是自由文本，
      不会用「MME：xxx」这种借物表格式）？

做法：
 (a) 定向核查：实验02 里明确说「链接/插件包放在评论区」的视频，看评论里到底有什么
 (b) 敏感核查：拿简介里出现过的全部工具名（全局词表），去评论原文里做朴素子串搜索
     —— 这比格式匹配宽松得多，如果这样都搜不到，才能确认「评论里没有工具名」
"""
import urllib.request, json, os, re, time, random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

D = os.path.dirname(os.path.abspath(__file__))
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}
TIMEOUT = 70
WORKERS = 8

# 实验02 里这三条视频的简介明确承诺「放在评论区」
TARGETED = ["BV1EZ4y1L7T6", "BV1um421V7So", "BV1y2Kr6CEdR"]

URL_RE = re.compile(r"https?://[^\s，。、）)\]}】\"'<]+")
NAME_TYPE_AUTHOR = re.compile(
    r"([A-Za-z][A-Za-z0-9_\-\.]{2,29})\s*[（(]([^）)]{1,14})[）)]\s*[：:]\s*([^|｜\n]+)")
FIELD_RE = re.compile(
    r"^[【\[]?\s*(MME|mme|Shader|shader|渲染|材质|特效|Effect|effect|PostEffect|"
    r"软件|插件|Tool|工具)\s*[】\]]?\s*[：:\s]\s*(.+)$")
SPLIT = re.compile(r"[/／、,，;；|｜\s]+")
ENG = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{2,29}$")
STOP = set("""the and for with you are not but all can how what this that from your
mmd pmx vmd pmd blender miku mikumikudance dance video music model motion
camera stage bgm bilibili com www http https bowlroll pan baidu github
new old ver version test demo final fix fixed upd update
please thanks thank good nice very more less than about
""".split())


def is_tool(t):
    if not ENG.match(t) or t.lower() in STOP or len(t) < 3:
        return False
    return not re.fullmatch(r"[vV]?\d+(\.\d+)*", t)


def extract(text):
    tools, urls = set(), URL_RE.findall(text or "")
    for m in NAME_TYPE_AUTHOR.finditer(text or ""):
        if is_tool(m.group(1)):
            tools.add(m.group(1))
    for line in (text or "").splitlines():
        m = FIELD_RE.match(line.strip())
        if not m:
            continue
        for t in SPLIT.split(URL_RE.sub(" ", m.group(2))):
            t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
            if is_tool(t):
                tools.add(t)
    return tools, urls


def get_cookie():
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://www.bilibili.com/", headers=UA), timeout=15)
        for c in (r.headers.get_all("Set-Cookie") or []):
            if "buvid3" in c:
                return c.split(";")[0]
    except Exception:
        pass


def grab(v, headers):
    aid = v.get("aid")
    url = "https://api.bilibili.com/x/v2/reply?type=1&oid=%d&sort=2&ps=20&pn=1" % aid
    for attempt in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT)
            d = json.loads(r.read().decode("utf-8"))
            if d.get("code") != 0:
                return v["bvid"], None
            data = d.get("data") or {}
            msgs = []
            top = ((data.get("upper") or {}).get("top")) or data.get("top")
            if top and (top.get("content") or {}).get("message"):
                msgs.append(("UP置顶", top["content"]["message"]))
            for rp in (data.get("replies") or []):
                m = (rp.get("content") or {}).get("message")
                if m:
                    msgs.append(("评论", m))
            return v["bvid"], msgs
        except Exception:
            time.sleep(1)
    return v["bvid"], None


def main():
    vids = json.load(open(os.path.join(D, "data_aid.json"), encoding="utf-8"))
    by_bv = {v["bvid"]: v for v in vids}

    # 全局工具词表（来自简介）
    vocab = set()
    for v in vids:
        t, _ = extract(v.get("desc", ""))
        vocab |= t
    vocab = {t for t in vocab if len(t) >= 4}          # 太短的容易误命中
    print("全局工具词表（长度>=4）: %d 个" % len(vocab))

    # 样本：3 个定向 + 37 个随机
    rest = [v for v in vids if v["bvid"] not in TARGETED]
    random.seed(7)
    random.shuffle(rest)
    sample = [by_bv[b] for b in TARGETED if b in by_bv] + rest[:37]
    print("核查样本: %d 个（含 3 个定向）" % len(sample))

    cookie = get_cookie()
    headers = dict(UA)
    if cookie:
        headers["Cookie"] = cookie

    got = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(grab, v, headers) for v in sample]
        for i, f in enumerate(as_completed(futs), 1):
            bv, msgs = f.result()
            got[bv] = msgs
            if i % 10 == 0:
                print("  %d/%d  %.1f min" % (i, len(sample), (time.time() - t0) / 60))

    ok = {b: m for b, m in got.items() if m}

    # ---- (a) 定向核查 ----
    print("\n" + "=" * 72)
    print("(a) 定向核查：简介明确说「放在评论区」的视频")
    print("=" * 72)
    for bv in TARGETED:
        v = by_bv.get(bv)
        if not v:
            print("[%s] 不在样本里" % bv); continue
        print("\n[%s] %s  (view=%d)" % (bv, v["title"][:56], v["view"]))
        d = v.get("desc", "").replace("\n", " ⏎ ")
        print("  简介片段: %s" % d[-200:])
        msgs = got.get(bv)
        if msgs is None:
            print("  评论: 抓取失败")
            continue
        print("  评论条数(第1页): %d" % len(msgs))
        for kind, m in msgs[:6]:
            urls = URL_RE.findall(m)
            print("    [%s] %s" % (kind, m.replace("\n", " ⏎ ")[:150]))
            if urls:
                print("         URLs: %s" % urls[:4])
        dt, _ = extract(v.get("desc", ""))
        ct = set()
        for _, m in msgs:
            t, _ = extract(m)
            ct |= t
        print("  → 简介工具 %s | 评论工具 %s" % (sorted(dt)[:5] or "无", sorted(ct)[:5] or "无"))

    # ---- (b) 敏感核查：朴素子串搜索 ----
    print("\n" + "=" * 72)
    print("(b) 敏感核查：用全局工具词表在评论原文里做朴素子串搜索")
    print("=" * 72)
    n_cmt = 0
    n_hit_video = 0
    hits = Counter()
    hit_examples = []
    n_with_url = 0
    for bv, msgs in ok.items():
        n_cmt += 1
        blob = "\n".join(m for _, m in msgs)
        if URL_RE.search(blob):
            n_with_url += 1
        found = set()
        low = blob.lower()
        for t in vocab:
            if t.lower() in low:
                found.add(t)
                hits[t] += 1
        if found:
            n_hit_video += 1
            if len(hit_examples) < 8:
                v = by_bv[bv]
                hit_examples.append((bv, v["title"][:50], sorted(found)[:8]))

    print("成功抓到评论的视频: %d" % n_cmt)
    print("评论里含 URL 的视频: %d (%.1f%%)" % (n_with_url, n_with_url / n_cmt * 100))
    print("评论里命中任一工具名的视频: %d (%.1f%%)" % (n_hit_video, n_hit_video / n_cmt * 100))
    print("命中的工具名分布: %s" % dict(hits.most_common(15)))
    print("\n命中样例:")
    for bv, ti, f in hit_examples:
        print("  [%s] %s → %s" % (bv, ti, f))

    out = {
        "vocab_size": len(vocab),
        "sample": len(sample), "ok": len(ok),
        "videos_with_url_in_comments": n_with_url,
        "url_rate": round(n_with_url / n_cmt * 100, 2) if n_cmt else 0,
        "videos_with_toolname_in_comments": n_hit_video,
        "toolname_rate": round(n_hit_video / n_cmt * 100, 2) if n_cmt else 0,
        "tool_hits": hits.most_common(30),
        "hits_examples": [{"bvid": b, "title": t, "tools": f} for b, t, f in
                          [(b, t, f) for b, t, f in hit_examples]],
    }
    json.dump(out, open(os.path.join(D, "data_verify.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nsaved: data_verify.json")


if __name__ == "__main__":
    main()
