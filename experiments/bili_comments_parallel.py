# -*- coding: utf-8 -*-
"""
实验 03（补测·并发版）：评论区抽取

诊断：评论接口单次响应约 50 秒（view 接口仅 4 秒），串行 180 次需 2.5 小时。
      改为线程池并发后约 12 分钟。

复用 data_aid.json（431 视频缓存，含 aid）。
"""
import urllib.request
import json, time, re, os, sys, random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}
D = os.path.dirname(os.path.abspath(__file__))
SAMPLE = int(os.environ.get("SAMPLE", "120"))
WORKERS = int(os.environ.get("WORKERS", "8"))
TIMEOUT = int(os.environ.get("TIMEOUT", "70"))


def get_cookie():
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://www.bilibili.com/", headers=UA), timeout=15)
        for c in (r.headers.get_all("Set-Cookie") or []):
            if "buvid3" in c:
                return c.split(";")[0]
    except Exception:
        pass
    return None


def fetch_json(url, headers, retries=1, timeout=TIMEOUT):
    for i in range(retries + 1):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
            return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries:
                return {"_exc": type(e).__name__}
            time.sleep(1)


# ---------------- 抽取规则 ----------------
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
    if re.fullmatch(r"[vV]?\d+(\.\d+)*", t):
        return False
    return True


def extract(text):
    if not text:
        return set(), []
    tools, urls = set(), URL_RE.findall(text)
    for m in NAME_TYPE_AUTHOR.finditer(text):
        if is_tool(m.group(1)):
            tools.add(m.group(1))
    for line in text.splitlines():
        m = FIELD_RE.match(line.strip())
        if not m:
            continue
        for t in SPLIT.split(URL_RE.sub(" ", m.group(2))):
            t = t.strip(" 　.。·-—_()（）[]【】\"'“”")
            if is_tool(t):
                tools.add(t)
    return tools, urls


# ---------------- 抓评论 ----------------

def grab(v, headers):
    aid = v.get("aid")
    if not aid:
        return v["bvid"], {"_err": "no_aid"}
    url = "https://api.bilibili.com/x/v2/reply?type=1&oid=%d&sort=2&ps=20&pn=1" % aid
    d = fetch_json(url, headers, retries=1)
    if not d or d.get("code") != 0:
        return v["bvid"], {"_err": (d or {}).get("code") or (d or {}).get("_exc")}
    data = d.get("data") or {}
    msgs = []
    top = ((data.get("upper") or {}).get("top")) or data.get("top")
    if top and (top.get("content") or {}).get("message"):
        msgs.append(top["content"]["message"])
    for r in (data.get("replies") or []):
        m = (r.get("content") or {}).get("message")
        if m:
            msgs.append(m)
    return v["bvid"], {"total": (data.get("page") or {}).get("count", 0), "msgs": msgs}


def main():
    vids = json.load(open(os.path.join(D, "data_aid.json"), encoding="utf-8"))
    print("loaded %d videos" % len(vids))

    for v in vids:
        dt, du = extract(v.get("desc", ""))
        v["_dt"] = sorted(dt)
        v["_du"] = du
    base_hit = sum(1 for v in vids if v["_dt"])
    print("[baseline] 简介解析出工具: %d/%d = %.1f%%"
          % (base_hit, len(vids), base_hit / len(vids) * 100))

    # 抽样：优先「简介有工具词但解析不出」的，其余随机补足
    prio, rest = [], []
    for v in vids:
        d = v.get("desc", "")
        if any(k in d for k in ["MME", "mme", "渲染", "插件", "Shader", "材质", "配布"]) and not v["_dt"]:
            prio.append(v)
        else:
            rest.append(v)
    random.seed(42)
    random.shuffle(rest)
    sample = (prio + rest)[:SAMPLE]
    print("[sample] %d 个（优先组 %d）｜并发 %d" % (len(sample), min(len(prio), SAMPLE), WORKERS))

    cookie = get_cookie()
    headers = dict(UA)
    if cookie:
        headers["Cookie"] = cookie
        print("cookie:", cookie[:28], "...")

    cmt = {}
    errs = Counter()
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(grab, v, headers): v for v in sample}
        done = 0
        for f in as_completed(futs):
            bv, res = f.result()
            cmt[bv] = res
            done += 1
            if "_err" in res:
                errs[str(res["_err"])] += 1
            if done % 10 == 0:
                print("  %d/%d  %.1f min  err=%d" % (done, len(sample), (time.time() - t0) / 60, sum(errs.values())))

    ok = [v for v in sample if v["bvid"] in cmt and "_err" not in cmt[v["bvid"]]]
    for v in ok:
        c = cmt[v["bvid"]]
        ct, cu = set(), []
        for m in c["msgs"]:
            t, u = extract(m)
            ct |= t
            cu.extend(u)
        v["_ct"] = sorted(ct)
        v["_cu"] = cu
        v["_cn"] = len(c["msgs"])
        v["_ctotal"] = c["total"]

    d_only = [v for v in ok if v["_dt"] and not v["_ct"]]
    c_only = [v for v in ok if v["_ct"] and not v["_dt"]]
    both = [v for v in ok if v["_dt"] and v["_ct"]]
    neither = [v for v in ok if not v["_dt"] and not v["_ct"]]
    union = d_only + c_only + both

    desc_rate = sum(1 for v in ok if v["_dt"]) / len(ok) * 100
    union_rate = len(union) / len(ok) * 100

    desc_all = set()
    for v in vids:
        desc_all |= set(v["_dt"])
    cmt_all = set()
    for v in ok:
        cmt_all |= set(v["_ct"])
    excl = sorted(cmt_all - desc_all)

    cmt_domains = Counter()
    for v in ok:
        for u in v["_cu"]:
            m = re.match(r"https?://([^/]+)", u)
            if m:
                cmt_domains[m.group(1).lower()] += 1

    # 置顶评论里带配布地址的比例
    with_url = sum(1 for v in ok if v["_cu"])

    print("\n" + "=" * 70)
    print("结果（评论抽样 %d 个，成功 %d，失败 %s）" % (len(sample), len(ok), dict(errs)))
    print("=" * 70)
    print("简介解析率（抽样内）   : %.1f%%" % desc_rate)
    print("简介+评论 合并解析率   : %.1f%%" % union_rate)
    print("→ 提升                 : +%.1f 个百分点" % (union_rate - desc_rate))
    print()
    print("  只有简介能解析出工具 : %d" % len(d_only))
    print("  只有评论能解析出工具 : %d   ← 关键" % len(c_only))
    print("  两边都有             : %d" % len(both))
    print("  两边都没有           : %d" % len(neither))
    print("  评论里含 URL 的视频  : %d / %d" % (with_url, len(ok)))
    print()
    print("不同工具名: 简介 %d 个 / 评论 %d 个 / 评论独有 %d 个"
          % (len(desc_all), len(cmt_all), len(excl)))
    if excl:
        print("评论独有工具:", ", ".join(excl[:50]))
    print()
    print("评论里的分发域名 top15:")
    for a, b in cmt_domains.most_common(15):
        print("  %-32s %d" % (a, b))

    out = {
        "baseline_desc_rate_all": round(base_hit / len(vids) * 100, 2),
        "sample": len(sample), "ok": len(ok), "errors": dict(errs),
        "desc_rate_in_sample": round(desc_rate, 2),
        "union_rate": round(union_rate, 2),
        "lift_pp": round(union_rate - desc_rate, 2),
        "desc_only": len(d_only), "comment_only": len(c_only),
        "both": len(both), "neither": len(neither),
        "videos_with_url_in_comments": with_url,
        "tools_desc": len(desc_all), "tools_comment": len(cmt_all),
        "comment_exclusive_tools": excl,
        "comment_domains": cmt_domains.most_common(25),
        "examples": [{
            "bvid": v["bvid"], "title": v["title"][:58], "view": v["view"],
            "desc_tools": v["_dt"][:8], "cmt_tools": v["_ct"][:8],
            "cmt_n": v["_cn"], "cmt_total": v["_ctotal"],
        } for v in (c_only + both)[:25]],
    }
    json.dump(out, open(os.path.join(D, "data_comments.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nsaved: data_comments.json  (%.1f min)" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
