#!/usr/bin/env python3
"""
国航盯盘·每日金融简报
覆盖：持仓分析 | 核心驱动 | 全球市场 | 资金流向 | 板块轮动 | 政治要闻 | 风险预警
"""
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

# ==========================================
# 数据采集
# ==========================================

def get_positions():
    """持仓 + 同行"""
    stocks = {}
    codes = [("sh601111","中国国航"),("sh600029","南方航空"),("sh600115","中国东航"),
             ("sh600009","上海机场"),("sh600029","南方航空"),("sz000099","中信海直")]
    for code,name in codes:
        try:
            d = sina(code); p = float(d[3]); pv = float(d[2]); vol = int(d[4])
            ch = round((p-pv)/pv*100,2)
            stocks[name] = {"price":p,"pct":ch,"vol":vol,"code":code}
        except: pass
    return stocks

def get_oil():
    import akshare as ak
    o = {}
    for s,n in [("CL","WTI"),("B","布伦特"),("NG","天然气")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            o[n] = {"p":round(l["close"],2),"c":round((l["close"]-p["close"])/p["close"]*100,2)}
        except: pass
    return o

def get_macro():
    """汇率、黄金、美债"""
    m = {}
    try:
        d = sina("USDCNY"); m["人民币"] = float(d[1])
    except: pass
    try:
        d = sina("hf_XAU"); m["黄金"] = {"p":float(d[0]),"c":float(d[2])}
    except: pass
    # 美元指数
    try:
        d = sina("DINIW"); m["美元指数"] = {"p":float(d[1]),"c":round(float(d[2]),2)}
    except: pass
    return m

def get_indices():
    import akshare as ak
    idx = {}
    # A股
    for c,n in [("sh000001","上证"),("sz399001","深证"),("sz399006","创业板"),("sh000688","科创50")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]
            idx[n] = {"p":round(l["close"],2),"c":round((l["close"]-l["open"])/l["open"]*100,2)}
        except: pass
    # 港股 + 美股
    for code,name,is_pct in [("hkHSI","恒生指数",True),("hkHSCEI","国企指数",True),
                              (".DJI","道琼斯",False),( ".IXIC","纳斯达克",False),(".INX","标普500",False)]:
        try:
            d = sina(code)
            if is_pct:
                idx[name] = {"p":float(d[1]),"c":float(d[3])}
            else:
                idx[name] = {"p":round(float(d[1]),2),"c":round(float(d[2]),2)}
        except: pass
    return idx

def get_market_breadth():
    """涨跌统计"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            up = len(df[df["涨跌幅"] > 0])
            down = len(df[df["涨跌幅"] < 0])
            flat = len(df[df["涨跌幅"] == 0])
            limit_up = len(df[df["涨跌幅"] >= 9.9])
            limit_down = len(df[df["涨跌幅"] <= -9.9])
            return {"涨":up,"跌":down,"平":flat,"涨停":limit_up,"跌停":limit_down}
    except: pass
    return None

def get_north_flow():
    """北向资金"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            return round(float(latest.get("value",0))/100000000,2)  # 亿
    except: pass
    return None

def get_sectors():
    """板块涨跌排行"""
    try:
        import akshare as ak
        df = ak.stock_sector_spot_em(sector="行业板块")
        if df is not None and not df.empty:
            df_sorted = df.sort_values("涨跌幅",ascending=False)
            top3 = [(str(r["板块名称"]),round(float(r["涨跌幅"]),2)) for _,r in df_sorted.head(3).iterrows()]
            bot3 = [(str(r["板块名称"]),round(float(r["涨跌幅"]),2)) for _,r in df_sorted.tail(3).iterrows()]
            return top3, bot3
    except: pass
    return None, None

def get_all_news():
    import akshare as ak
    items = []
    for src in [ak.stock_news_em, ak.news_economic_baidu]:
        try:
            df = src()
            if df is not None and not df.empty:
                cols = df.columns.tolist()
                tc = next((c for c in ["新闻标题","title"] if c in cols), cols[1] if len(cols)>1 else cols[0])
                for _,r in df.head(40).iterrows():
                    t = str(r.get(tc,"")).strip()
                    if len(t)>8: items.append(t[:120])
        except: pass
    seen = set(); uniq = []
    for i in items:
        k = i[:30]
        if k not in seen: seen.add(k); uniq.append(i)
    return uniq

def classify_news(items):
    """专业新闻分类"""
    categories = {
        "🔥 地缘政治": ["伊朗","中东","波斯湾","以色列","巴勒斯坦","哈马斯","乌克兰","俄罗斯","北约","朝鲜","南海","台海","关税","制裁","贸易战","导弹","冲突","战争"],
        "🏛️ 宏观政策": ["政治局","国常会","国务院","央行","降息","降准","加息","美联储","利率","CPI","通胀","PMI","GDP","财政","货币","LPR","MLF","逆回购","国债","地方债"],
        "✈️ 航空旅游": ["航空","国航","机票","民航","航班","机场","波音","空客","旅游","出行","酒店","携程","免签","签证","国际航线"],
        "🛢️ 能源商品": ["原油","油价","OPEC","石油","天然气","能源","钻井","EIA","库存","产量","煤炭","电力"],
        "🇨🇳 A股市场": ["A股","大盘","上证","深证","创业板","主板","北向","万亿","放量","缩量","涨停","跌停","指数","3000","4000"],
        "🇺🇸 美股科技": ["美股","纳指","道指","标普","苹果","特斯拉","英伟达","AI","芯片","微软","科技股"],
        "🏭 产业经济": ["新能源","汽车","房地产","半导体","消费","医药","银行","券商","保险","光伏","锂电","白酒","制造"],
        "🌍 国际财经": ["欧盟","欧洲","日本","印度","WTO","G7","G20","IMF","世界银行","衰退","复苏","债务","违约"],
    }
    result = {}
    used = set()
    for cat, kws in categories.items():
        matched = []
        for n in items:
            if id(n) in used: continue
            if any(k in n for k in kws):
                matched.append(n)
                used.add(id(n))
                if len(matched) >= 4: break
        if matched: result[cat] = matched
    rest = [n for n in items if id(n) not in used][:4]
    if rest: result["📋 其他"] = rest
    return result

def analyze(positions, oil, macro, idx, breadth, north, sectors, news):
    """综合研判"""
    neg, pos, neu = [], [], []
    # 国航自身
    ac = positions.get("中国国航",{})
    if ac:
        if ac.get("pct",0) > 5: pos.append("国航大涨5%+")
        elif ac.get("pct",0) < -5: neg.append("国航大跌5%+")
    # 油价
    wti = oil.get("WTI",{}).get("c",0)
    if wti > 3: neg.append(f"WTI涨{wti}%，燃油成本承压")
    elif wti < -3: pos.append(f"WTI跌{abs(wti)}%，成本利好")
    # 人民币
    cny = macro.get("人民币",7)
    if cny > 7.35: neg.append(f"人民币贬至{cny}，国际收入缩水")
    elif cny < 6.95: pos.append("人民币升破7，利好国际航线")
    # 北向
    if north is not None:
        if north > 50: pos.append(f"北向净流入{north}亿，外资看多")
        elif north < -50: neg.append(f"北向净流出{abs(north)}亿，外资撤离")
    # 涨跌比
    if breadth:
        ratio = breadth["涨"]/max(breadth["跌"],1)
        if ratio > 5: pos.append("个股普涨，市场情绪高涨")
        elif ratio < 0.2: neg.append("个股普跌，恐慌蔓延")
        if breadth["跌停"] > 50: neg.append(f"{breadth['跌停']}只跌停，踩踏风险")
        if breadth["涨停"] > 50: pos.append(f"{breadth['涨停']}只涨停，赚钱效应强")
    # 大盘
    sh = idx.get("上证",{}).get("c",0)
    if sh > 2: pos.append("上证涨超2%，强势")
    elif sh < -2: neg.append("上证跌超2%，破位风险")
    return neg, pos, neu

# ==========================================
# 构建推送
# ==========================================

def build(positions, oil, macro, idx, breadth, north, sectors, news_cats, neg, pos, neu):
    now = datetime.now(BEIJING_TZ); ds = now.strftime("%m/%d %H:%M")
    emoji = "🌅" if now.hour<12 else "🌙"
    n_neg = len(neg); n_pos = len(pos)

    if n_neg >= 3: verdict, vc = "🔴 谨慎 | 多重利空叠加","#e74c3c"
    elif n_neg >= 1: verdict, vc = "🟠 偏空 | 存在下行风险","#e67e22"
    elif n_pos >= 3: verdict, vc = "🟢 看好 | 多重利好共振","#27ae60"
    elif n_pos >= 1: verdict, vc = "🔵 偏多 | 积极因素占优","#3498db"
    else: verdict, vc = "⚪ 中性 | 多空交织，观望","#95a5a6"

    css = """*{margin:0;padding:0}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#0d1117;color:#c9d1d9;padding:10px;font-size:13px;max-width:500px;margin:0 auto}
.header{text-align:center;padding:16px 12px;margin-bottom:10px;background:#161b22;border-radius:12px;border:1px solid #30363d}
.header .title{font-size:17px;font-weight:700;color:#f0f6fc}
.header .time{font-size:11px;color:#8b949e;margin-top:4px}
.verdict{padding:14px;border-radius:10px;text-align:center;margin-bottom:10px}
.verdict .main{font-size:18px;font-weight:700}
.verdict .sub{font-size:12px;margin-top:4px;opacity:0.8}
.factors{display:flex;flex-wrap:wrap;gap:4px;justify-content:center;margin-top:6px}
.badge{font-size:10px;padding:3px 8px;border-radius:10px}
.badge-red{background:#e74c3c22;color:#e74c3c;border:1px solid #e74c3c33}
.badge-green{background:#27ae6022;color:#27ae60;border:1px solid #27ae6033}
.badge-gray{background:#88888822;color:#888;border:1px solid #88888833}
.card{background:#161b22;border-radius:10px;padding:12px;margin-bottom:8px;border:1px solid #21262d}
.card h3{font-size:13px;color:#f0f6fc;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.card h3 .tag{font-size:10px;padding:2px 6px;border-radius:4px;background:#30363d}
.t-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:13px}
.t-left{color:#8b949e}.t-right{text-align:right}.t-bold{font-weight:600;color:#f0f6fc}
.up{color:#e74c3c}.down{color:#27ae60}.flat{color:#8b949e}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.mini-card{background:#0d1117;border-radius:8px;padding:8px;border:1px solid #21262d}
.mini-card .label{font-size:10px;color:#8b949e}.mini-card .value{font-size:15px;font-weight:700;margin-top:2px}
.news-item{font-size:12px;padding:4px 0;border-bottom:1px solid #21262d33;line-height:1.5;color:#b0b0c0}
.news-item:last-child{border-bottom:none}
.section-divider{text-align:center;font-size:10px;color:#484f58;padding:6px 0}
.footer{text-align:center;font-size:10px;color:#484f58;padding:12px 0}"""

    # 头部
    hdr = f'<div class="header"><div class="title">✈️ 国航盯盘 · 每日金融简报</div><div class="time">{ds} 北京时间</div></div>'

    # 评级
    verdict_h = f'<div class="verdict" style="background:linear-gradient(135deg,{vc}18,{vc}08);border:1.5px solid {vc}33"><div class="main" style="color:{vc}">{verdict}</div>'
    if neg or pos:
        verdict_h += '<div class="factors">'
        for f in neg: verdict_h += f'<span class="badge badge-red">⚠ {f}</span>'
        for f in pos: verdict_h += f'<span class="badge badge-green">✓ {f}</span>'
        verdict_h += '</div>'
    verdict_h += '</div>'

    # 1) 持仓
    pos_html = '<div class="card"><h3>💼 航运板块</h3>'
    for n in ["中国国航","南方航空","中国东航","上海机场"]:
        i = positions.get(n)
        if i:
            c = "up" if i["pct"]>0 else ("down" if i["pct"]<0 else "flat")
            arrow = "↑" if i["pct"]>0 else ("↓" if i["pct"]<0 else "→")
            pos_html += f'<div class="t-row"><span class="t-left">{n}</span><span class="t-right"><span class="t-bold">{i["price"]}</span> <span class="{c}">{i["pct"]:+.2f}% {arrow}</span></span></div>'
    pos_html += '</div>'

    # 2) 核心驱动
    drv_html = '<div class="card"><h3>⚡ 核心驱动</h3><div class="cols">'
    if "WTI" in oil:
        w = oil["WTI"]; c = "up" if w["c"]>0 else "down"
        drv_html += f'<div class="mini-card"><div class="label">🛢️ WTI原油</div><div class="value {c}">${w["p"]} <small>{w["c"]:+.1f}%</small></div></div>'
    if "布伦特" in oil:
        b = oil["布伦特"]; c = "up" if b["c"]>0 else "down"
        drv_html += f'<div class="mini-card"><div class="label">🛢️ 布伦特</div><div class="value {c}">${b["p"]} <small>{b["c"]:+.1f}%</small></div></div>'
    if "人民币" in macro:
        drv_html += f'<div class="mini-card"><div class="label">💱 人民币</div><div class="value t-bold">{macro["人民币"]:.4f}</div></div>'
    if "美元指数" in macro:
        dxy = macro["美元指数"]; c = "up" if dxy["c"]>0 else "down"
        drv_html += f'<div class="mini-card"><div class="label">💵 美元指数</div><div class="value {c}">{dxy["p"]:.1f} <small>{dxy["c"]:+.1f}%</small></div></div>'
    drv_html += '</div></div>'

    # 3) 全球指数
    idx_html = '<div class="card"><h3>📈 全球指数</h3>'
    for n in ["上证","深证","创业板","科创50","恒生指数","道琼斯","纳斯达克","标普500"]:
        i = idx.get(n)
        if i:
            c = "up" if i["c"]>0 else "down"
            idx_html += f'<div class="t-row"><span class="t-left">{n}</span><span class="t-right"><span class="t-bold">{i["p"]:.0f}</span> <span class="{c}">{i["c"]:+.2f}%</span></span></div>'
    idx_html += '</div>'

    # 4) 市场温度
    temp_html = '<div class="card"><h3>🌡️ 市场温度</h3><div class="cols">'
    if breadth:
        temp_html += f'<div class="mini-card"><div class="label">📊 涨跌比</div><div class="value"><span class="up">{breadth["涨"]}</span>/<span class="down">{breadth["跌"]}</span>/<span class="flat">{breadth["平"]}</span></div></div>'
        temp_html += f'<div class="mini-card"><div class="label">🎯 涨跌停</div><div class="value"><span class="up">{breadth["涨停"]}</span>/<span class="down">{breadth["跌停"]}</span></div></div>'
    if north is not None:
        c = "up" if north>0 else "down"
        temp_html += f'<div class="mini-card"><div class="label">💵 北向资金</div><div class="value {c}">{north:+.1f}亿</div></div>'
    # 板块
    top3, bot3 = sectors
    if top3:
        temp_html += f'<div class="mini-card"><div class="label">🔥 领涨</div><div class="value" style="font-size:11px;color:#e74c3c">{" · ".join(f"{n}" for n,_ in top3[:2])}</div></div>'
    if bot3:
        temp_html += f'<div class="mini-card"><div class="label">❄️ 领跌</div><div class="value" style="font-size:11px;color:#27ae60">{" · ".join(f"{n}" for n,_ in bot3[:2])}</div></div>'
    temp_html += '</div></div>'

    # 5) 新闻（分类折叠）
    news_html = ""
    for cat_name, items in list(news_cats.items())[:6]:
        if not items: continue
        news_html += f'<div class="card"><h3>{cat_name} <span class="tag">{len(items)}条</span></h3>'
        for n in items[:4]:
            news_html += f'<div class="news-item">▸ {n}</div>'
        news_html += '</div>'

    ft = '<div class="footer">⚠️ 仅供参考，不构成投资建议<br>腾讯云24h运行 | 每天9:00/20:00自动推送<br>数据来源：东方财富·新浪财经·百度财经</div>'

    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{verdict_h}{pos_html}{drv_html}{idx_html}{temp_html}{news_html}{ft}</body></html>'

# ==========================================
# 主流程
# ==========================================

def main():
    print("⏳ 采集数据...")
    positions = get_positions(); print(f"  持仓: {list(positions.keys())}")
    oil = get_oil(); print(f"  商品: {list(oil.keys())}")
    macro = get_macro(); print(f"  宏观: {list(macro.keys())}")
    idx = get_indices(); print(f"  指数: {list(idx.keys())}")
    breadth = get_market_breadth(); print(f"  涨跌: {breadth}")
    north = get_north_flow(); print(f"  北向: {north}")
    sectors = get_sectors(); print(f"  板块top3/bot3获取中...")
    items = get_all_news(); print(f"  新闻: {len(items)}条")
    cats = classify_news(items)
    for k,v in cats.items(): print(f"    {k}: {len(v)}")

    neg, pos, neu = analyze(positions, oil, macro, idx, breadth, north, sectors, cats)

    html = build(positions, oil, macro, idx, breadth, north, sectors, cats, neg, pos, neu)
    now = datetime.now(BEIJING_TZ)
    emoji = "🌅" if now.hour<12 else "🌙"
    push(f"{emoji} 国航盯盘 - {now.strftime('%m/%d %H:%M')}", html)

if __name__ == "__main__":
    main()
