#!/usr/bin/env python3
"""国航盯盘 - 全维度覆盖"""
from datetime import datetime, timezone, timedelta
import json, os, urllib.request

BEIJING_TZ = timezone(timedelta(hours=8))

def token():
    t = os.environ.get("PUSHPLUS_TOKEN","")
    if t: return t
    cf = os.path.expanduser("~/.briefing_token")
    return open(cf).read().strip() if os.path.exists(cf) else ""

def push(title, content):
    t = token()
    if not t: print("无Token"); return
    d = json.dumps({"token":t,"title":title,"content":content,"template":"html"}).encode()
    r = urllib.request.Request("https://www.pushplus.plus/send",data=d,headers={"Content-Type":"application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(r,timeout=15).read())
        print("📲 已推送" if resp.get("code")==200 else f"失败:{resp.get('msg')}")
    except Exception as e: print(f"异常:{e}")

def sina(symbol):
    import urllib.request as ur
    req = ur.Request(f"https://hq.sinajs.cn/list={symbol}",headers={"Referer":"https://finance.sina.com.cn"})
    return ur.urlopen(req,timeout=10).read().decode("gbk").split('"')[1].split(",")

# ====== 数据 ======

def get_airchina():
    result = {}
    for code,name in [("sh601111","中国国航"),("sh600029","南方航空"),("sh600115","中国东航")]:
        try:
            d = sina(code); p = float(d[3]); pv = float(d[2])
            result[name] = {"price":p,"pct":round((p-pv)/pv*100,2)}
        except: pass
    return result

def get_oil():
    import akshare as ak
    result = {}
    for s,n in [("CL","WTI"),("B","布伦特")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            result[n] = {"price":round(l["close"],2),"pct":round((l["close"]-p["close"])/p["close"]*100,2)}
        except: pass
    return result

def get_index():
    import akshare as ak
    idx = {}
    for c,n in [("sh000001","上证"),("sz399001","深证"),("sz399006","创业板")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]; pct = round((l["close"]-l["open"])/l["open"]*100,2)
            idx[n] = {"price":round(l["close"],2),"pct":pct}
        except: pass
    for code,name in [("hkHSI","恒生"),(".DJI","道指"),(".IXIC","纳指"),(".INX","标普")]:
        try:
            d = sina(code)
            if code.startswith("hk"):
                idx[name] = {"price":float(d[1]),"pct":float(d[3])}
            else:
                idx[name] = {"price":round(float(d[1]),2),"pct":round(float(d[2]),2)}
        except: pass
    return idx

def get_fx():
    try:
        d = sina("USDCNY"); return float(d[1])
    except: return None

def get_gold():
    try:
        d = sina("hf_XAU"); return {"price":float(d[0]),"pct":float(d[2])}
    except: return None

def get_all_news():
    """从多个源抓新闻"""
    import akshare as ak
    items = []
    # 东方财富
    try:
        df = ak.stock_news_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            tc = "新闻标题" if "新闻标题" in cols else cols[1]
            for _,r in df.head(50).iterrows():
                t = str(r.get(tc,""))
                if t and len(t)>8: items.append(t[:120])
    except: pass
    # 百度财经
    try:
        df2 = ak.news_economic_baidu()
        if df2 is not None and not df2.empty:
            for _,r in df2.head(20).iterrows():
                t = str(r.get("title",""))
                if t and len(t)>8: items.append(t[:120])
    except: pass
    # 去重
    seen = set()
    uniq = []
    for i in items:
        key = i[:30]
        if key not in seen:
            seen.add(key)
            uniq.append(i)
    return uniq

def filter_news(items):
    """全维度筛选"""
    cats = {
        "✈️ 航空民航": ["航空","国航","南航","东航","机票","民航","航班","机场","波音","空客","旅游","出行","燃油","航油","航线","起飞"],
        "🛢️ 原油能源": ["原油","油价","OPEC","欧佩克","石油","钻井","能源","产量","库存","EIA"],
        "🔥 美伊中东": ["伊朗","中东","波斯湾","霍尔木兹","以色列","巴以","哈马斯","真主党","也门","胡塞","叙利亚","伊拉克","沙特"],
        "🌐 国际政治": ["美国","特朗普","拜登","白宫","国会","五角大楼","北约","欧盟","俄罗斯","普京","乌克兰","朝鲜","韩国","日本","印度","南海","台海","台湾","关税","贸易战","制裁","WTO","G7","G20"],
        "🏛️ 国内政策": ["政治局","国常会","国务院","发改委","商务部","央行","证监会","财政部","住建部","工信部","政策","调控","监管","法规","改革"],
        "💹 宏观财经": ["美联储","降息","加息","利率","CPI","通胀","GDP","PMI","就业","非农","人民币","汇率","社融","M2","信贷","国债"],
        "📊 A股异动": ["暴涨","暴跌","熔断","跌停","涨停","北向","主力","资金","放量","万亿","恐慌","崩盘","新高","新低","涨停潮","跌停潮"],
        "🇺🇸 美股异动": ["美股","道指","纳指","标普","科技股","苹果","特斯拉","英伟达","微软","亚马逊","Meta","七巨头"],
    }
    result = {}
    used = set()
    for cat_name, keywords in cats.items():
        matched = []
        for n in items:
            if id(n) in used: continue
            if any(k in n for k in keywords):
                matched.append(n)
                used.add(id(n))
                if len(matched) >= 5: break
        if matched:
            result[cat_name] = matched
    # 剩下的也算"其他重要"
    rest = [n for n in items if id(n) not in used][:5]
    if rest:
        result["📋 其他重要资讯"] = rest
    return result

def analyze(ac, oil, fx, news_cats):
    """判断对国航的影响"""
    neg, pos, neu = [], [], []
    # 油价
    if oil:
        wti = oil.get("WTI",{}).get("pct",0)
        if wti > 3: neg.append("油价暴涨>3%，航空成本压力大")
        elif wti > 1: neu.append("油价小幅上涨")
        elif wti < -3: pos.append("油价大跌>3%，成本明显缓解")
        elif wti < -1: neu.append("油价小幅回落")
    # 汇率
    if fx:
        if fx > 7.35: neg.append(f"人民币贬值至{fx}，国际航线收入缩水")
        elif fx < 7.0: pos.append(f"人民币升值至{fx}，国际航线受益")
    # 新闻中找信号
    all_titles = []
    for v in news_cats.values():
        all_titles.extend(v)
    all_text = " ".join(all_titles)
    bad_signals = ["紧张","冲突","制裁","打击","暴跌","崩盘","恐慌","升级","加税","炮火","战争"]
    good_signals = ["复苏","增长","利好","新高","突破","缓和","回暖","反弹","放量","涨停"]
    bad_count = sum(1 for k in bad_signals if k in all_text)
    good_count = sum(1 for k in good_signals if k in all_text)
    if bad_count > good_count + 3: neg.append("负面信号偏多，市场情绪谨慎")
    if good_count > bad_count + 3: pos.append("积极信号偏多，市场情绪乐观")
    return neg, pos, neu

def build(ac, oil, fx, idx, gold, news_cats, neg, pos, neu):
    now = datetime.now(BEIJING_TZ); ds = now.strftime("%m/%d %H:%M")
    emoji = "🌅" if now.hour<12 else "🌙"
    n_neg = len(neg); n_pos = len(pos)
    if n_neg >= 3: verdict,vc = "⚠️ 谨慎 | 多条利空","#e74c3c"
    elif n_neg >= 1: verdict,vc = "⚡ 请注意 | 有风险因素","#e67e22"
    elif n_pos >= 2: verdict,vc = "✅ 看好 | 利好居多","#27ae60"
    else: verdict,vc = "➖ 中性 | 暂无明确信号","#7f8c8d"

    css = """*{margin:0;padding:0}body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#1a1a2e;color:#e0e0e0;padding:12px;font-size:14px}
.card{background:#16213e;border-radius:10px;padding:14px;margin-bottom:10px}
.card h3{font-size:14px;margin-bottom:8px;border-bottom:1px solid #0f3460;padding-bottom:6px}
.row{display:flex;justify-content:space-between;align-items:center;padding:4px 0}
.name{color:#a0a0b0;font-size:13px}.val{font-weight:bold;font-size:15px}
.red{color:#e94560}.green{color:#0f9}.gray{color:#888}
.verdict{padding:14px;border-radius:10px;text-align:center;margin-bottom:10px}
.verdict h2{font-size:18px}
.reason{padding:6px 10px;margin:3px 0;border-radius:6px;font-size:12px}
.reason-bad{background:#e9456015;color:#e94560}.reason-good{background:#0f9915;color:#0f9}.reason-neu{background:#88888815;color:#999}
.news-item{font-size:13px;padding:5px 0;border-bottom:1px solid #0f346025;line-height:1.5;color:#c0c0d0}
.news-item:last-child{border-bottom:none}
.hr{border:none;border-top:1px solid #0f3460;margin:8px 0}
.footer{text-align:center;font-size:11px;color:#555;padding:15px 0 5px}"""

    hdr = f'<div class="verdict" style="background:{vc}15;border:2px solid {vc}"><h2 style="color:{vc}">{emoji} {verdict}</h2><div style="font-size:12px;color:#888;margin-top:4px">{ds} 北京时间</div></div>'

    # 判断依据
    reason = ""
    for f in neg: reason += f'<div class="reason reason-bad">⚠️ {f}</div>'
    for f in pos: reason += f'<div class="reason reason-good">✅ {f}</div>'
    for f in neu: reason += f'<div class="reason reason-neu">➖ {f}</div>'

    # 航空
    ac_h = '<div class="card"><h3>✈️ 航空板块</h3>'
    for n in ["中国国航","南方航空","中国东航"]:
        i = ac.get(n)
        if i: ac_h += f'<div class="row"><span class="name">{n}</span><span class="val">{i["price"]}</span><span class="{"red" if i["pct"]>0 else "green"}">{i["pct"]:+.2f}%</span></div>'
    ac_h += f'<div class="hr"></div><div style="font-size:11px;color:#666">💡 航空股三大命门：油价 | 汇率 | 国际局势</div></div>'

    # 原油
    oil_h = '<div class="card"><h3>🛢️ 原油</h3>'
    for n in ["WTI","布伦特"]:
        i = oil.get(n)
        if i: oil_h += f'<div class="row"><span class="name">{n}</span><span class="val">${i["price"]}</span><span class="{"red" if i["pct"]>0 else "green"}">{i["pct"]:+.2f}%</span></div>'
    if gold: oil_h += f'<div class="hr"></div><div class="row"><span class="name">🥇 黄金</span><span class="val">${gold["price"]}</span><span class="{"red" if gold["pct"]>0 else "green"}">{gold["pct"]:+.2f}%</span></div>'
    if fx: oil_h += f'<div class="row"><span class="name">💱 人民币</span><span class="val">{fx:.4f}</span><span class="gray">↔美元</span></div>'
    oil_h += '</div>'

    # 指数
    idx_h = '<div class="card"><h3>📈 全球市场</h3>'
    for n in ["上证","深证","创业板","恒生","道指","纳指","标普"]:
        i = idx.get(n)
        if i: idx_h += f'<div class="row"><span class="name">{n}</span><span class="val">{i["price"]:.0f}</span><span class="{"red" if i["pct"]>0 else "green"}">{i["pct"]:+.2f}%</span></div>'
    idx_h += '</div>'

    # 新闻
    news_html = ""
    for cat_name, items in news_cats.items():
        news_html += f'<div class="card"><h3>{cat_name}</h3>'
        for n in items:
            news_html += f'<div class="news-item">• {n}</div>'
        news_html += '</div>'

    ft = '<div class="footer">⚠️ 仅供参考，不构成投资建议<br>每天9:00 / 20:00 自动推送 | 腾讯云24h运行</div>'

    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{reason}{ac_h}{oil_h}{idx_h}{news_html}{ft}</body></html>'

def main():
    print("⏳ 抓取数据...")
    ac = get_airchina(); print(f"  航空: {list(ac.keys())}")
    oil = get_oil(); print(f"  原油: {list(oil.keys())}")
    fx = get_fx(); print(f"  汇率: {fx}")
    idx = get_index(); print(f"  指数: {list(idx.keys())}")
    gold = get_gold(); print(f"  黄金: {gold['price'] if gold else 'N/A'}")
    items = get_all_news(); print(f"  新闻: {len(items)}条")
    cats = filter_news(items);
    for k,v in cats.items(): print(f"    {k}: {len(v)}条")

    neg, pos, neu = analyze(ac, oil, fx, cats)

    html = build(ac, oil, fx, idx, gold, cats, neg, pos, neu)
    now = datetime.now(BEIJING_TZ)
    emoji = "🌅" if now.hour<12 else "🌙"
    push(f"{emoji} 国航盯盘 - {now.strftime('%m/%d %H:%M')}", html)

if __name__ == "__main__":
    main()
