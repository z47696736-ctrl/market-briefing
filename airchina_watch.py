#!/usr/bin/env python3
"""你专属的市场简报 - 只发对国航有影响的信息"""
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
    """通用新浪行情"""
    import urllib.request as ur
    url = f"https://hq.sinajs.cn/list={symbol}"
    req = ur.Request(url, headers={"Referer":"https://finance.sina.com.cn"})
    resp = ur.urlopen(req, timeout=10)
    return resp.read().decode("gbk").split('"')[1].split(",")

def blue(pct):
    """涨红跌绿"""
    if not isinstance(pct,(int,float)): return str(pct)
    return f'<span style="color:#e74c3c;font-weight:bold">+{pct}%</span>' if pct>0 else f'<span style="color:#27ae60;font-weight:bold">{pct}%</span>'

# ========== 核心数据 ==========

def get_airchina():
    """国航 + 航空板块"""
    result = {"airchina":None, "south":None, "east":None}
    for code, name in [("sh601111","中国国航"),("sh600029","南方航空"),("sh600115","中国东航")]:
        try:
            d = sina(code)
            price = float(d[3]); prev = float(d[2])
            pct = round((price-prev)/prev*100,2)
            result[name] = {"price":price,"pct":pct}
        except: pass
    return result

def get_oil():
    """原油（国航成本核心）"""
    result = {}
    import akshare as ak
    for s,n in [("CL","WTI原油"),("B","布伦特")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            result[n] = {"price":round(l["close"],2),"pct":round((l["close"]-p["close"])/p["close"]*100,2)}
        except: pass
    return result

def get_fx():
    """汇率（国航国际航线收入）"""
    try:
        d = sina("USDCNY"); return float(d[1])
    except: return None

def get_index():
    """大盘情绪"""
    idx = {}
    import akshare as ak
    for c,n in [("sh000001","上证"),("sz399001","深证"),("sz399006","创业板")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]; pct = round((l["close"]-l["open"])/l["open"]*100,2)
            idx[n] = {"price":round(l["close"],2),"pct":pct}
        except: pass
    # 港股
    try:
        d = sina("hkHSI"); idx["恒生"] = {"price":float(d[1]),"pct":float(d[3])}
    except: pass
    return idx

def get_news():
    """筛选真正有用的新闻"""
    import akshare as ak
    items = []
    try:
        df = ak.stock_news_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            tc = "新闻标题" if "新闻标题" in cols else cols[1] if len(cols)>1 else cols[0]
            for _,r in df.head(40).iterrows():
                t = str(r.get(tc,""))
                if t and len(t)>8: items.append(t[:100])
    except: pass
    return items

def filter_news(all_news):
    """按重要性分类"""
    # 直接影响国航的关键词
    airline_kw = ["航空","国航","机票","民航","航班","机场","旅游","出行","燃油","航油"]
    oil_kw = ["原油","油价","OPEC","欧佩克","产油","石油","钻井","能源"]
    me_kw = ["伊朗","中东","波斯湾","霍尔木兹","以色列","巴以","制裁"]
    trade_kw = ["关税","贸易","中美","加税","脱钩","出口","进口","WTO","谈判"]
    policy_kw = ["央行","降息","美联储","利率","人民币","汇率","CPI","通胀","PMI","政策"]
    market_kw = ["A股","大盘","暴涨","暴跌","熔断","恐慌","崩盘","回调","牛市","熊市"]

    airline = [n for n in all_news if any(k in n for k in airline_kw)][:3]
    oil_news = [n for n in all_news if any(k in n for k in oil_kw)][:3]
    me_news = [n for n in all_news if any(k in n for k in me_kw)][:2]
    trade_news = [n for n in all_news if any(k in n for k in trade_kw)][:2]
    policy_news = [n for n in all_news if any(k in n for k in policy_kw)][:3]
    market_news = [n for n in all_news if any(k in n for k in market_kw)][:3]

    return airline, oil_news, me_news, trade_news, policy_news, market_news

# ========== 分析 ==========

def analyze(ac, oil, fx, idx, airline, oil_news, me_news, trade_news):
    """一句话分析今天对国航的影响"""
    factors = []

    # 油价判断
    if oil:
        wti = oil.get("WTI原油",{}).get("pct",0)
        brent = oil.get("布伦特",{}).get("pct",0)
        avg_oil = (wti+brent)/2 if oil.get("布伦特") else wti
        if avg_oil > 2:
            factors.append(("negative","油价大涨，航空成本上升，利空"))
        elif avg_oil < -2:
            factors.append(("positive","油价大跌，航空成本下降，利好"))
        elif avg_oil > 0.5:
            factors.append(("neutral","油价微涨，略施压成本"))
        elif avg_oil < -0.5:
            factors.append(("neutral","油价微跌，成本略有缓解"))

    # 汇率判断
    if fx:
        # 人民币贬值 > 7.2 对国际航线不利（收入缩水）
        if fx > 7.3:
            factors.append(("negative","人民币贬值破7.3，国际航线收入承压"))
        elif fx < 7.0:
            factors.append(("positive","人民币升值，国际航线收入利好"))

    # 局势判断
    if me_news:
        factors.append(("negative","中东局势紧张，油价风险上升"))

    if trade_news:
        if any("加" in n or "升级" in n or "制裁" in n for n in trade_news):
            factors.append(("negative","贸易摩擦升温，市场情绪承压"))
        elif any("缓和" in n or "突破" in n or "达成" in n for n in trade_news):
            factors.append(("positive","贸易局势缓和，利好市场"))

    # 航空板块新闻
    if airline:
        positive_kw = ["增长","利好","复苏","新高","恢复","增开","加密"]
        negative_kw = ["取消","停飞","亏损","下滑","事故","延误","限飞"]
        pos_count = sum(1 for n in airline for k in positive_kw if k in n)
        neg_count = sum(1 for n in airline for k in negative_kw if k in n)
        if neg_count > pos_count:
            factors.append(("negative","航空板块负面消息较多"))
        elif pos_count > neg_count:
            factors.append(("positive","航空板块有利好消息"))

    neg = [f for t,f in factors if t=="negative"]
    pos = [f for t,f in factors if t=="positive"]
    neu = [f for t,f in factors if t=="neutral"]

    return neg, pos, neu

# ========== 构建推送 ==========

def build(ac_data, oil, fx, idx, airline, oil_news, me_news, trade_news, policy_news, market_news, neg, pos, neu):
    now = datetime.now(BEIJING_TZ)
    ds = now.strftime("%m月%d日 %H:%M")
    emoji = "🌅" if now.hour<12 else "🌙"

    # 整体判断
    if len(neg) >= 3:
        verdict = "⚠️ 谨慎 | 利空因素较多"
        v_color = "#e74c3c"
    elif len(neg) >= 1:
        verdict = "⚡ 偏空 | 注意风险"
        v_color = "#e67e22"
    elif len(pos) >= 2:
        verdict = "✅ 偏多 | 利好为主"
        v_color = "#27ae60"
    else:
        verdict = "➖ 中性 | 观望为主"
        v_color = "#7f8c8d"

    css = """*{margin:0;padding:0}body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#1a1a2e;color:#e0e0e0;padding:12px;font-size:14px}
.card{background:#16213e;border-radius:10px;padding:14px;margin-bottom:10px}
.card h3{font-size:14px;margin-bottom:8px;border-bottom:1px solid #0f3460;padding-bottom:6px}
.card h3 span{color:#e94560;font-size:12px;margin-left:6px}
.row{display:flex;justify-content:space-between;align-items:center;padding:4px 0}
.name{color:#a0a0b0;font-size:13px}.val{font-weight:bold;font-size:15px}
.red{color:#e94560}.green{color:#0f9}.gray{color:#888}
.chip{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;margin:2px}.chip-bad{background:#e9456022;color:#e94560}.chip-good{background:#0f9922;color:#0f9}.chip-warn{background:#e67e2222;color:#e67e22}
.verdict{padding:12px;border-radius:10px;text-align:center;margin-bottom:10px}
.verdict h2{font-size:16px}
.news-item{font-size:13px;padding:4px 0;border-bottom:1px solid #0f346040;line-height:1.5;color:#b0b0c0}
.news-item:last-child{border-bottom:none}
.hr{border:none;border-top:1px solid #0f3460;margin:8px 0}
.footer{text-align:center;font-size:11px;color:#666;padding:15px 0 5px}"""

    # 头部
    hdr = f'<div class="verdict" style="background:{v_color}22;border:1px solid {v_color}"><h2 style="color:{v_color}">{emoji} {verdict}</h2><div style="font-size:12px;color:#888;margin-top:4px">{ds} 北京</div></div>'

    # 利空利好因素
    factor_html = ""
    if neg or pos or neu:
        factor_html = '<div class="card"><h3>📋 今日判断依据</h3>'
        for f in neg:
            factor_html += f'<div class="row"><span class="name">⚠️</span><span class="red" style="font-size:13px">{f}</span></div>'
        for f in pos:
            factor_html += f'<div class="row"><span class="name">✅</span><span class="green" style="font-size:13px">{f}</span></div>'
        for f in neu:
            factor_html += f'<div class="row"><span class="name">➖</span><span style="font-size:13px;color:#888">{f}</span></div>'
        factor_html += '</div>'

    # 国航 + 航空板块
    ac_html = '<div class="card"><h3>✈️ 航空板块 <span>你的持仓</span></h3>'
    for name, info in [("中国国航",ac_data.get("中国国航")),("南方航空",ac_data.get("南方航空")),("中国东航",ac_data.get("中国东航"))]:
        if info:
            c = "red" if info["pct"]>0 else "green"
            ac_html += f'<div class="row"><span class="name">{name}</span><span class="val">{info["price"]}</span><span class="{c}">{info["pct"]:+.2f}%</span></div>'
    ac_html += '<div class="hr"></div><div style="font-size:12px;color:#888">💡 油价跌=成本降=利好航空 | 人民币升值=国际航线受益</div></div>'

    # 原油
    oil_html = '<div class="card"><h3>🛢️ 原油价格 <span>成本核心</span></h3>'
    for n,i in [("WTI原油",oil.get("WTI原油")),("布伦特",oil.get("布伦特"))]:
        if i:
            c = "red" if i["pct"]>0 else "green"
            oil_html += f'<div class="row"><span class="name">{n}</span><span class="val">${i["price"]}</span><span class="{c}">{i["pct"]:+.2f}%</span></div>'
    oil_html += '</div>'

    # 大盘
    idx_html = '<div class="card"><h3>📈 市场行情</h3>'
    for n in ["上证","深证","创业板","恒生"]:
        if n in idx:
            i = idx[n]; c = "red" if i["pct"]>0 else "green"
            idx_html += f'<div class="row"><span class="name">{n}</span><span class="val">{i["price"]:.0f}</span><span class="{c}">{i["pct"]:+.2f}%</span></div>'
    if fx:
        idx_html += f'<div class="hr"></div><div class="row"><span class="name">💱 人民币汇率</span><span class="val">{fx:.4f}</span><span class="gray">美元</span></div>'
    idx_html += '</div>'

    # 新闻（只保留有用的）
    news_sections = []
    if airline: news_sections.append(("✈️ 航空动态", airline))
    if oil_news: news_sections.append(("🛢️ 原油能源", oil_news))
    if me_news: news_sections.append(("🔥 中东局势", me_news))
    if trade_news: news_sections.append(("🌐 贸易局势", trade_news))
    if policy_news: news_sections.append(("🏛️ 宏观政策", policy_news))
    if market_news: news_sections.append(("📊 市场热点", market_news))

    news_html = ""
    for title, items in news_sections:
        news_html += f'<div class="card"><h3>{title}</h3>'
        for n in items:
            news_html += f'<div class="news-item">• {n}</div>'
        news_html += '</div>'

    if not news_sections:
        news_html = '<div class="card"><h3>📰 今日资讯</h3><div class="news-item" style="color:#666">暂无相关新闻</div></div>'

    ft = '<div class="footer">⚠️ 仅供参考，不构成投资建议<br>数据：东方财富/新浪财经 | 每天早上9点、晚上8点推送</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{factor_html}{ac_html}{oil_html}{idx_html}{news_html}{ft}</body></html>"""

def main():
    print("⏳ 抓取数据...")
    ac = get_airchina(); print(f"  航空: {'国航' if ac.get('中国国航') else 'N/A'}")
    oil = get_oil(); print(f"  原油: {list(oil.keys())}")
    fx = get_fx(); print(f"  汇率: {fx}")
    idx = get_index(); print(f"  大盘: {list(idx.keys())}")
    all_n = get_news(); print(f"  新闻总数: {len(all_n)}")
    airline, oil_n, me_n, trade_n, policy_n, market_n = filter_news(all_n)
    print(f"  筛选: 航空{len(airline)} 原油{len(oil_n)} 中东{len(me_n)} 贸易{len(trade_n)} 宏观{len(policy_n)} 市场{len(market_n)}")

    neg, pos, neu = analyze(ac, oil, fx, idx, airline, oil_n, me_n, trade_n)

    html = build(ac, oil, fx, idx, airline, oil_n, me_n, trade_n, policy_n, market_n, neg, pos, neu)

    now = datetime.now(BEIJING_TZ)
    emoji = "🌅" if now.hour<12 else "🌙"
    push(f"{emoji} 国航盯盘 - {now.strftime('%m/%d %H:%M')}", html)

if __name__ == "__main__":
    main()
