#!/usr/bin/env python3
"""每日市场简报 - 修复版"""
from datetime import datetime, timezone, timedelta
import json, os, urllib.request

BEIJING_TZ = timezone(timedelta(hours=8))

def load_token():
    t = os.environ.get("PUSHPLUS_TOKEN", "")
    if t: return t
    cf = os.path.expanduser("~/.briefing_token")
    if os.path.exists(cf):
        return open(cf).read().strip()
    return ""

def save_token():
    cf = os.path.expanduser("~/.briefing_token")
    t = os.environ.get("PUSHPLUS_TOKEN", "")
    if not t:
        t = input("PushPlus Token: ").strip()
    if t:
        with open(cf, "w") as f: f.write(t)
    return t

def push(title, content):
    token = load_token() or save_token()
    if not token:
        print("无Token，跳过推送"); return
    d = json.dumps({"token":token,"title":title,"content":content,"template":"html"}).encode()
    r = urllib.request.Request("https://www.pushplus.plus/send", data=d, headers={"Content-Type":"application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(r, timeout=15).read())
        print("📲 已推送" if resp.get("code")==200 else f"推送失败:{resp.get('msg')}")
    except Exception as e:
        print(f"推送异常:{e}")

def a_share():
    import akshare as ak
    res = []
    for c,n in [("sh000001","上证"),("sz399001","深证"),("sz399006","创业板"),("sh000300","沪深300")]:
        df = ak.stock_zh_index_daily(symbol=c)
        l = df.iloc[-1]
        pct = round((l["close"]-l["open"])/l["open"]*100,2)
        res.append({"n":n,"c":round(l["close"],2),"p":pct})
    return res

def us_market():
    import akshare as ak
    res = []
    for s,n in [(".DJI","道琼斯"),(".IXIC","纳指"),(".INX","标普500")]:
        try:
            df = ak.index_us_stock_sina(symbol=s)
            l = df.iloc[-1]; pct = round(float(l.get("change_pct",0)),2)
            res.append({"n":n,"c":round(l["close"],2),"p":pct})
        except: pass
    return res

def oil_price():
    import akshare as ak
    res = []
    for s,n in [("WTI原油","WTI"),("布伦特原油","布伦特")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            ch = round((l["close"]-p["close"])/p["close"]*100,2)
            res.append({"n":n,"pr":round(l["close"],2),"p":ch})
        except: pass
    return res

def air_china():
    import akshare as ak
    try:
        df = ak.stock_zh_a_hist(symbol="601111",period="daily",adjust="qfq")
        l,p = df.iloc[-1],df.iloc[-2]
        return {"c":round(l["收盘"],2),"p":round((l["收盘"]-p["收盘"])/p["收盘"]*100,2)}
    except: return None

def all_news():
    import akshare as ak
    items = []
    for func_name in ["stock_news_em", "stock_info_global_em"]:
        try:
            fn = getattr(ak, func_name, None)
            if fn:
                df = fn()
                if df is not None and not df.empty:
                    for _,r in df.head(15).iterrows():
                        t = str(r.get("title","") or r.get("content","") or "")
                        if t and len(t)>5:
                            items.append(t[:80])
        except: pass
    # 过滤美伊相关
    kw = ["伊朗","美国","中东","美伊","原油","油价","OPEC","制裁","以色列","波斯湾","霍尔木兹"]
    me = [i for i in items if any(k in i for k in kw)][:5]
    top = items[:8]
    return top, me

def build_html(ash, usm, oil, ac, news, me_news, bt):
    def c(p):
        if isinstance(p,(int,float)):
            return f'<span style="color:red">+{p}%</span>' if p>0 else (f'<span style="color:green">{p}%</span>' if p<0 else '0%')
        return str(p)

    ra = "".join(f"<tr><td>{i['n']}</td><td>{i['c']}</td><td>{c(i['p'])}</td></tr>" for i in ash)
    ru = "".join(f"<tr><td>{i['n']}</td><td>{i['c']}</td><td>{c(i['p'])}</td></tr>" for i in usm)

    if bt=="morning":
        t1 = f"<h3>🇺🇸 隔夜美股</h3><table border=1 cellpadding=4>{ru}</table>"
        t2 = f"<h3>🇨🇳 A股盘前</h3><table border=1 cellpadding=4>{ra}</table>"
    else:
        t1 = f"<h3>🇨🇳 A股</h3><table border=1 cellpadding=4>{ra}</table>"
        t2 = f"<h3>🇺🇸 美股</h3><table border=1 cellpadding=4>{ru}</table>"

    ach = ""
    if ac:
        ach = f"<p><b>✈️ 国航601111:</b> {ac['c']}元 {c(ac['p'])}</p>"

    oor = "".join(f"<tr><td>{i['n']}</td><td>${i['pr']}</td><td>{c(i['p'])}</td></tr>" for i in oil)
    oh = f"<h3>🛢️ 原油（油价↗=利空航空）</h3><table border=1 cellpadding=4>{oor}</table>"

    meh = ""
    if me_news:
        meh = "<h3>🔥 美伊/中东</h3><ul>" + "".join(f"<li>{n}</li>" for n in me_news) + "</ul>"

    nl = "".join(f"<li>{n}</li>" for n in news[:6]) if news else "<li>(暂无)</li>"

    return f"""{ach}{oh}{meh}{t1}{t2}<h3>📰 市场新闻</h3><ul>{nl}</ul><p style="color:#999">⚠️ 仅供参考</p>"""

def main():
    print("⏳ 抓取数据...")
    now = datetime.now(BEIJING_TZ)
    bt = "morning" if now.hour < 12 else "evening"
    ds = now.strftime("%m月%d日 %H:%M")
    bt_cn = "🌅 盘前简报" if bt=="morning" else "🌙 收盘简报"

    ash = a_share(); print(f"  A股: {len(ash)}项")
    usm = us_market(); print(f"  美股: {len(usm)}项")
    oil = oil_price(); print(f"  原油: {len(oil)}项")
    ac = air_china(); print(f"  国航: {'OK' if ac else 'N/A'}")
    news, me = all_news(); print(f"  新闻: {len(news)}条, 美伊: {len(me)}条")

    # 终端打印摘要
    print(f"\n{'='*40}")
    print(f"  {bt_cn} - {ds}")
    for i in ash:
        s = "🔴" if i["p"]>0 else ("🟢" if i["p"]<0 else "⚪")
        print(f"  {s} {i['n']}: {i['c']} ({i['p']:+.2f}%)")
    if ac: print(f"  ✈️ 国航: {ac['c']} ({ac['p']:+.2f}%)")
    for i in oil:
        print(f"  🛢️ {i['n']}: ${i['pr']} ({i['p']:+.2f}%)")
    if news: print(f"  📰 {news[0][:50]}...")
    print(f"{'='*40}")

    html = build_html(ash, usm, oil, ac, news, me, bt)
    push(f"📊 {bt_cn} - {ds}", html)

if __name__ == "__main__":
    main()
