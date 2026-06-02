#!/usr/bin/env python3
"""每日市场简报 - V4 完整版"""
from datetime import datetime, timezone, timedelta
import json, os, urllib.request, time

BEIJING_TZ = timezone(timedelta(hours=8))

def load_token():
    t = os.environ.get("PUSHPLUS_TOKEN", "")
    if t: return t
    cf = os.path.expanduser("~/.briefing_token")
    if os.path.exists(cf):
        t = open(cf).read().strip()
        if t and len(t) > 10: return t
    return ""

def push(title, content):
    token = load_token()
    if not token:
        print("无Token"); return
    d = json.dumps({"token":token,"title":title,"content":content,"template":"html"}).encode()
    r = urllib.request.Request("https://www.pushplus.plus/send",data=d,headers={"Content-Type":"application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(r,timeout=15).read())
        print("📲 已推送" if resp.get("code")==200 else f"失败:{resp.get('msg')}")
    except Exception as e:
        print(f"异常:{e}")

def a_share():
    import akshare as ak
    res = []
    for c,n in [("sh000001","上证指数"),("sz399001","深证成指"),("sz399006","创业板指"),("sh000300","沪深300")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]
            pct = round((l["close"]-l["open"])/l["open"]*100,2)
            res.append({"n":n,"c":round(l["close"],2),"p":pct,"v":int(l.get("volume",0))})
        except Exception as e: print(f"  A股{n}失败:{e}")
    return res

def us_market():
    import akshare as ak
    res = []
    for s,n in [(".DJI","道琼斯"),(".IXIC","纳斯达克"),(".INX","标普500")]:
        try:
            df = ak.index_us_stock_sina(symbol=s)
            l = df.iloc[-1]
            prev = df.iloc[-2]
            pct = round((l["close"]-prev["close"])/prev["close"]*100,2)
            res.append({"n":n,"c":round(l["close"],2),"p":pct})
        except Exception as e: print(f"  美股{n}失败:{e}")
    return res

def oil_price():
    import akshare as ak
    res = []
    for s,n in [("CL","WTI原油"),("B","布伦特原油")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            ch = round((l["close"]-p["close"])/p["close"]*100,2)
            res.append({"n":n,"pr":round(l["close"],2),"p":ch})
        except Exception as e: print(f"  原油{n}失败:{e}")
    return res

def air_china():
    """国航 - 用新浪接口"""
    try:
        import urllib.request as ur
        url = "https://hq.sinajs.cn/list=sh601111"
        req = ur.Request(url, headers={"Referer":"https://finance.sina.com.cn"})
        resp = ur.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        parts = data.split('"')[1].split(",")
        if len(parts) > 3:
            name = parts[0]
            price = float(parts[3])
            prev_close = float(parts[2])
            pct = round((price-prev_close)/prev_close*100,2)
            return {"n":name,"c":price,"p":pct}
    except Exception as e: print(f"  国航失败:{e}")
    return None

def hk_market():
    """港股恒生指数"""
    try:
        import urllib.request as ur
        url = "https://hq.sinajs.cn/list=hkHSI"
        req = ur.Request(url, headers={"Referer":"https://finance.sina.com.cn"})
        resp = ur.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        parts = data.split('"')[1].split(",")
        if len(parts) > 3:
            price = float(parts[1])
            pct = float(parts[3])
            return {"n":"恒生指数","c":price,"p":pct}
    except: pass
    return None

def gold_price():
    """黄金"""
    try:
        import urllib.request as ur
        url = "https://hq.sinajs.cn/list=hf_XAU"
        req = ur.Request(url, headers={"Referer":"https://finance.sina.com.cn"})
        resp = ur.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        parts = data.split('"')[1].split(",")
        if len(parts) > 3:
            price = float(parts[0])
            pct = float(parts[2])
            return {"n":"现货黄金","pr":price,"p":pct}
    except: pass
    return None

def yuan_rate():
    """人民币汇率"""
    try:
        import urllib.request as ur
        url = "https://hq.sinajs.cn/list=USDCNY"
        req = ur.Request(url, headers={"Referer":"https://finance.sina.com.cn"})
        resp = ur.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        parts = data.split('"')[1].split(",")
        if len(parts) > 2:
            return float(parts[1])
    except: pass
    return None

def all_news():
    import akshare as ak
    items = []
    # 东方财富新闻
    try:
        df = ak.stock_news_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            tc = "新闻标题" if "新闻标题" in cols else cols[1] if len(cols)>1 else cols[0]
            for _,r in df.head(20).iterrows():
                t = str(r.get(tc,""))
                if t and len(t)>8:
                    items.append(t[:100])
    except: pass
    # 百度财经新闻
    try:
        df2 = ak.news_economic_baidu()
        if df2 is not None and not df2.empty:
            for _,r in df2.head(10).iterrows():
                t = str(r.get("title",""))
                if t and len(t)>8:
                    items.append(t[:100])
    except: pass

    # 分类筛选
    me_kw = ["伊朗","美国","中东","美伊","以色列","制裁","波斯湾","霍尔木兹","OPEC","石油"]
    macro_kw = ["央行","美联储","降息","加息","CPI","GDP","通胀","人民币","汇率","PMI","政策","国常会","政治局"]
    a_kw = ["A股","大盘","北向","涨停","跌停","板块","券商","基金"]

    me = [i for i in items if any(k in i for k in me_kw)][:5]
    macro = [i for i in items if any(k in i for k in macro_kw) and not any(k in i for k in me_kw)][:4]
    astock = [i for i in items if any(k in i for k in a_kw) and i not in macro and i not in me][:4]
    other = [i for i in items if i not in me and i not in macro and i not in astock][:6]

    return me, macro, astock, other

def build_html(ash, usm, oil, ac, hk, gold, yuan, me, macro, astock, other, bt):
    def c(p):
        if not isinstance(p,(int,float)): return str(p)
        if p>0: return f'<span style="color:#e74c3c">+{p}%</span>'
        if p<0: return f'<span style="color:#27ae60">{p}%</span>'
        return '0%'
    def arrow(p):
        if not isinstance(p,(int,float)): return ''
        return '↗' if p>0 else ('↘' if p<0 else '→')

    # CSS
    css = """body{margin:0;padding:15px;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:#f0f2f5;color:#333;font-size:14px}
.card{background:#fff;border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}
.card h3{margin:0 0 10px 0;font-size:15px;color:#1a1a1a}
.card h3 .badge{font-size:11px;padding:2px 6px;border-radius:4px;margin-right:4px}
.badge-green{background:#e8f5e9;color:#2e7d32}.badge-red{background:#fce4ec;color:#c62828}.badge-blue{background:#e3f2fd;color:#1565c0}.badge-orange{background:#fff3e0;color:#e65100}
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:4px 6px;border-bottom:1px solid #f5f5f5}
td:last-child{text-align:right;white-space:nowrap}
.news li{font-size:13px;line-height:1.6;color:#444;margin-bottom:4px}
.footer{text-align:center;font-size:11px;color:#bdbdbd;padding:10px}
.header{text-align:center;padding:8px 0;font-size:13px;color:#666}
.header b{color:#333;font-size:16px}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:3px;margin-right:4px}
.tag-hot{background:#ffebee;color:#c62828}.tag-macro{background:#e8eaf6;color:#283593}"""

    # 头部
    now = datetime.now(BEIJING_TZ)
    hdr = f'<div class="header"><b>📊 每日市场简报</b><br>{now.strftime("%Y年%m月%d日 %H:%M")} 北京时间</div>'

    # 国航卡片
    ac_card = ""
    if ac:
        ac_sign = "🔴" if ac['p']>0 else ("🟢" if ac['p']<0 else "⚪")
        ac_card = f'<div class="card"><h3>✈️ 中国国航 {ac["n"]} <span class="badge badge-red">持仓关注</span></h3><table><tr><td>最新价</td><td style="text-align:right;font-size:18px;font-weight:bold">{ac["c"]}</td><td>{c(ac["p"])} {ac_sign}</td></tr></table></div>'

    # A股
    ra = ""
    for i in ash:
        ra += f'<tr><td>{i["n"]}</td><td>{i["c"]:.2f}</td><td>{c(i["p"])}</td></tr>'
    a_card = f'<div class="card"><h3>🇨🇳 A股主要指数</h3><table>{ra}</table></div>'

    # 美股
    ru = ""
    for i in usm:
        ru += f'<tr><td>{i["n"]}</td><td>{i["c"]:.2f}</td><td>{c(i["p"])}</td></tr>'
    us_card = f'<div class="card"><h3>🇺🇸 美股</h3><table>{ru}</table></div>'

    # 港股
    hk_str = ""
    if hk:
        hk_str = f'<tr><td>{hk["n"]}</td><td>{hk["c"]:.2f}</td><td>{c(hk["p"])}</td></tr>'

    # 商品
    com_rows = ""
    for i in oil:
        com_rows += f'<tr><td>🛢️ {i["n"]}</td><td>${i["pr"]:.2f}</td><td>{c(i["p"])}</td></tr>'
    if gold:
        com_rows += f'<tr><td>🥇 {gold["n"]}</td><td>${gold["pr"]:.2f}</td><td>{c(gold["p"])}</td></tr>'
    com_card = f'<div class="card"><h3>🛢️ 大宗商品 <span class="badge badge-orange">油价↗=利空航空</span></h3><table>{com_rows}</table></div>' if com_rows else ""

    # 汇率
    fx_str = ""
    if yuan:
        fx_str = f'<div class="card"><h3>💱 人民币汇率</h3><table><tr><td>美元/人民币</td><td style="text-align:right;font-size:16px">{yuan:.4f}</td></tr></table></div>'

    # 美伊
    me_card = ""
    if me:
        me_card = f'<div class="card"><h3>🔥 美伊/中东局势</h3><ul class="news">' + "".join(f"<li>{n}</li>" for n in me) + '</ul></div>'

    # 宏观
    mac_card = ""
    if macro:
        mac_card = f'<div class="card"><h3>🌍 全球宏观</h3><ul class="news">' + "".join(f"<li>{n}</li>" for n in macro) + '</ul></div>'

    # A股新闻
    an_card = ""
    if astock:
        an_card = f'<div class="card"><h3>📰 A股热点</h3><ul class="news">' + "".join(f"<li>{n}</li>" for n in astock) + '</ul></div>'

    # 其他
    ot_card = ""
    if other:
        ot_card = f'<div class="card"><h3>📋 更多资讯</h3><ul class="news">' + "".join(f"<li>{n}</li>" for n in other[:5]) + '</ul></div>'

    ft = '<div class="footer">⚠️ 仅供参考，不构成投资建议 | 数据来源：东方财富/新浪财经/百度财经</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{ac_card}{a_card}{us_card}{com_card}{fx_str}{me_card}{mac_card}{an_card}{ot_card}{ft}</body></html>"""

def main():
    print("⏳ 抓取数据...")
    now = datetime.now(BEIJING_TZ)
    bt = "morning" if now.hour < 12 else "evening"
    ds = now.strftime("%m月%d日 %H:%M")
    bt_cn = "🌅 盘前简报" if bt=="morning" else "🌙 收盘简报"

    print("  A股..."); ash = a_share()
    print("  美股..."); usm = us_market()
    print("  原油..."); oil = oil_price()
    print("  国航..."); ac = air_china()
    print("  港股..."); hk = hk_market()
    print("  黄金..."); gold = gold_price()
    print("  汇率..."); yuan = yuan_rate()
    print("  新闻..."); me, macro, astock, other = all_news()

    print(f"\n{'='*50}")
    print(f"  {bt_cn} - {ds}")
    for i in ash: print(f"  {i['n']}: {i['c']} ({i['p']:+.2f}%)")
    if ac: print(f"  ✈️ 国航: {ac['c']} ({ac['p']:+.2f}%)")
    for i in oil: print(f"  🛢️ {i['n']}: ${i['pr']} ({i['p']:+.2f}%)")
    if gold: print(f"  🥇 黄金: ${gold['pr']} ({gold['p']:+.2f}%)")
    if yuan: print(f"  💱 汇率: {yuan:.4f}")
    print(f"  📰 新闻:{len(me)}美伊/{len(macro)}宏观/{len(astock)}A股/{len(other)}其他")
    print(f"{'='*50}")

    html = build_html(ash, usm, oil, ac, hk, gold, yuan, me, macro, astock, other, bt)
    push(f"📊 {bt_cn} - {ds}", html)

if __name__ == "__main__":
    main()
