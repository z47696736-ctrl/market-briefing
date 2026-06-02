#!/usr/bin/env python3
"""国航盯盘 - 一切围绕601111"""
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
    """只有国航"""
    try:
        d = sina("sh601111"); p = float(d[3]); pv = float(d[2])
        high = float(d[4]); low = float(d[5]); vol = int(d[8]); amt = round(float(d[9])/10000,0)
        return {"price":p,"prev":pv,"pct":round((p-pv)/pv*100,2),"high":high,"low":low,"vol":vol,"amt":amt}
    except: return None

def get_oil_fx_gold():
    """国航的命门：油价和汇率"""
    result = {}
    # 原油
    import akshare as ak
    for s,n in [("CL","WTI原油"),("B","布伦特原油")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            result[n] = {"p":round(l["close"],2),"c":round((l["close"]-p["close"])/p["close"]*100,2)}
        except: pass
    # 人民币
    try: d = sina("USDCNY"); result["人民币"] = float(d[1])
    except: pass
    # 黄金 - 跳过（数据不准）
    return result

def get_index():
    import akshare as ak
    idx = {}
    for c,n in [("sh000001","上证指数"),("sz399001","深证成指"),("sz399006","创业板指")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]
            idx[n] = {"p":round(l["close"],2),"c":round((l["close"]-l["open"])/l["open"]*100,2)}
        except: pass
    for code,name in [("hkHSI","恒生指数"),(".DJI","道琼斯"),(".IXIC","纳斯达克")]:
        try:
            d = sina(code)
            idx[name] = {"p":round(float(d[1]),2),"c":round(float(d[3] if code.startswith("hk") else d[2]),2)}
        except: pass
    return idx

def get_breadth():
    import akshare as ak
    try:
        df = ak.stock_zh_a_spot_em()
        up = len(df[df["涨跌幅"]>0]); down = len(df[df["涨跌幅"]<0])
        limit_up = len(df[df["涨跌幅"]>=9.9]); limit_down = len(df[df["涨跌幅"]<=-9.9])
        return up, down, limit_up, limit_down
    except: return 0,0,0,0

def get_north():
    import akshare as ak
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        return round(float(df.iloc[-1].get("value",0))/100000000,2)
    except: return None

def get_news():
    """新浪财经新闻 - 多栏目采集"""
    import urllib.request as ur, json, re
    items = []

    # 不同栏目: 2509=全球财经, 2510=国内财经, 2512=国际财经, 2515=产经
    for lid in [2509, 2510, 2512]:
        try:
            url = f'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid={lid}&k=&num=20&page=1'
            req = ur.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
            data = json.loads(ur.urlopen(req, timeout=10).read().decode())
            for item in data.get('result',{}).get('data',[]):
                t = item.get('title','') or item.get('intro','')
                if t and len(t)>8 and len(t)<200: items.append(t)
        except: pass

    # 也保留东方财富作为补充
    try:
        import akshare as ak
        df = ak.stock_news_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            tc = "新闻标题" if "新闻标题" in cols else cols[1]
            for _,r in df.head(30).iterrows():
                t = str(r.get(tc,"")).strip()
                if len(t)>8 and len(t)<200: items.append(t)
    except: pass

    seen=set(); uniq=[]
    for i in items:
        k=i[:30]
        if k not in seen: seen.add(k); uniq.append(i)
    return uniq

def filter_for_airchina(all_news):
    """只保留对国航有影响的新闻 - 全维度覆盖"""
    direct = ["国航","601111","航空","机票","民航","航班","机场","波音","空客","东航","南航","海航","春秋","吉祥","廉价航空","飞行员","空乘","燃油","航油","旅游","出行","酒店","免签","签证","国际航线","国内航线","暑运","春运","国庆","五一","候机楼","跑道","空管","流量","准点率"]
    oil = ["原油","油价","OPEC","欧佩克","石油","钻井","产油","减产","EIA","库存","能源","天然气","煤炭","燃油","航油","制裁","伊朗","中东","波斯湾","以色列","霍尔木兹","沙特","也门","胡塞","叙利亚","伊拉克","科威特","阿联酋"]
    fx_trade = ["人民币","汇率","关税","中美","贸易战","贸易摩擦","出口","进口","WTO","谈判","脱钩","加税","反制","清单","301","调查","贸易逆差","贸易顺差","出海"]
    macro = ["央行","美联储","降息","降准","加息","利率","CPI","通胀","GDP","PMI","LPR","MLF","逆回购","政策","政治局","国常会","国务院","发改委","货币","财政","国债","地方债","社融","M2","信贷","消费"]
    market = ["A股","大盘","暴涨","暴跌","跌停潮","涨停潮","北向","万亿","放量","缩量","恐慌","新高","新低","3000","4000","熔断","翻红","翻绿","跳水","拉升","V型","深V","尾盘","午后","涨停","跌停","板块","赛道","龙头"]
    global_ = ["美股","纳指","道指","标普","科技股","特斯拉","英伟达","苹果","微软","Meta","亚马逊","谷歌","俄罗斯","乌克兰","朝鲜","韩国","日本","印度","欧洲","欧盟","北约","特朗普","拜登","大选","白宫","国会","五角大楼","台海","南海","菲律宾"]
    travel = ["旅游","景区","携程","同程","美团","酒店","民宿","消费","出境游","入境游","国内游","周边游","自由行","跟团游","邮轮","火车票","高铁"]

    cats = {
        "✈️ 航空旅游": direct + travel,
        "🛢️ 原油能源": oil,
        "💱 汇率贸易": fx_trade,
        "🏛️ 国内政策": macro,
        "📊 A股异动": market,
        "🌍 国际局势": global_,
    }
    result = {}; used=set()
    for cat,kws in cats.items():
        m=[]
        for n in all_news:
            if id(n) in used: continue
            if any(k in n for k in kws):
                m.append(n); used.add(id(n))
                if len(m)>=4: break
        if m: result[cat]=m
    return result

# ====== 分析 ======

def analyze(ac, oil_fx, idx, up, down, lu, ld, north, news):
    neg, pos, neu = [], [], []

    # 国航自身
    if ac:
        if ac["pct"] > 5: pos.append("国航今日大涨")
        elif ac["pct"] < -5: neg.append("国航今日大跌")
        if ac["pct"] > 2.5: pos.append(f"国航+{ac['pct']}%跑赢大盘")
        elif ac["pct"] < -2.5: neg.append(f"国航{ac['pct']}%跑输大盘")
    # 油价
    wti = oil_fx.get("WTI原油",{}).get("c",0)
    brent = oil_fx.get("布伦特原油",{}).get("c",0)
    avg_oil = (wti+brent)/2 if brent else wti
    if avg_oil > 3: neg.append(f"油价涨{avg_oil:.1f}%→燃油成本↑")
    elif avg_oil < -3: pos.append(f"油价跌{abs(avg_oil):.1f}%→燃油成本↓")
    elif avg_oil > 1: neu.append(f"油价微涨{avg_oil:.1f}%")
    elif avg_oil < -1: neu.append(f"油价微跌{abs(avg_oil):.1f}%")
    # 人民币
    cny = oil_fx.get("人民币",7.2)
    if cny > 7.3: neg.append(f"人民币{cny}贬值→国际收入↓")
    elif cny < 7.0: pos.append(f"人民币{cny}升值→国际收入↑")
    # 行情
    if up>0 and down>0 and up/down>5: pos.append("个股普涨情绪好")
    elif down>0 and up>0 and down/up>5: neg.append("个股普跌恐慌中")
    if lu>100: pos.append(f"{lu}只涨停赚钱效应强")
    if ld>50: neg.append(f"{ld}只跌停风险高")
    # 北向
    if north is not None:
        if north>80: pos.append(f"北向+{north}亿大幅流入")
        elif north<-80: neg.append(f"北向{north}亿大幅流出")
    # 大盘
    sh = idx.get("上证指数",{}).get("c",0)
    if sh>3: pos.append("上证暴涨市场强势")
    elif sh<-3: neg.append("上证暴跌系统性风险")

    # 新闻中的信号
    all_t = " ".join([t for v in news.values() for t in v])
    bad = sum(1 for w in ["冲突","战争","制裁","暴跌","崩盘","恐慌","升级","危机","暂停","取消","停飞"] if w in all_t)
    good = sum(1 for w in ["增长","利好","复苏","新高","突破","回暖","反弹","放量","增开","恢复"] if w in all_t)
    if bad>good+3: neg.append("负面消息明显偏多")
    if good>bad+3: pos.append("积极信号明显偏多")

    return neg, pos, neu

def verdict(neg, pos, ac):
    n=len(neg); p=len(pos)
    # 国航自身走势权重最大
    if ac and ac.get("pct",0) < -4: return "🔴 国航大跌","#e74c3c"
    if ac and ac.get("pct",0) > 4: return "🟢 国航大涨","#27ae60"
    if n>=3: return "🔴 利空叠加","#e74c3c"
    elif n>=1: return "🟠 注意风险","#e67e22"
    elif p>=3: return "🟢 利好共振","#27ae60"
    elif p>=1: return "🔵 偏积极","#3498db"
    return "⚪ 中性","#95a5a6"

# ====== 构建 ======

def build(ac, oil_fx, idx, up, down, lu, ld, north, news, neg, pos, neu):
    now = datetime.now(BEIJING_TZ)
    ds = now.strftime("%m/%d %H:%M")
    emoji = "🌅" if now.hour<12 else "🌙"
    v_text, vc = verdict(neg, pos, ac)

    css = """*{margin:0;padding:0}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#0d1117;color:#e0e0e0;padding:8px;font-size:13px}
.header{text-align:center;padding:12px;background:linear-gradient(180deg,#1a1f2e,#161b22);border-radius:12px;margin-bottom:8px}
.header h1{font-size:16px;color:#f0f6fc}.header .time{font-size:10px;color:#8b949e}
.ac-card{background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:14px;margin-bottom:8px;text-align:center;border:2px solid #21262d}
.ac-card .name{font-size:13px;color:#8b949e}.ac-card .price{font-size:28px;font-weight:800;margin:4px 0}.ac-card .change{font-size:14px;font-weight:600}
.ac-card .detail{display:flex;justify-content:center;gap:16px;margin-top:6px;font-size:11px;color:#8b949e}
.up{color:#e74c3c}.down{color:#27ae60}.flat{color:#8b949e}
.verdict{text-align:center;padding:8px;margin-bottom:6px;border-radius:8px;font-size:13px;font-weight:700}
.verdict .reasons{font-size:10px;margin-top:4px;font-weight:400;opacity:0.85}
.card{background:#161b22;border-radius:8px;padding:10px;margin-bottom:6px;border:1px solid #21262d}
.card h3{font-size:12px;color:#f0f6fc;margin-bottom:6px}
.row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px}
.row .l{color:#8b949e}.row .r{text-align:right;font-weight:600}
.news-item{font-size:11px;padding:3px 0;border-bottom:1px solid #21262d33;line-height:1.5;color:#b0b0c0}
.news-item:last-child{border-bottom:none}
.footer{text-align:center;font-size:10px;color:#484f58;padding:10px}"""

    # 头部
    hdr = f'<div class="header"><h1>✈️ 国航盯盘</h1><div class="time">{ds} 北京时间 · 腾讯云自动运行</div></div>'

    # 国航大卡片
    ac_html = ""
    if ac:
        c = "up" if ac["pct"]>0 else ("down" if ac["pct"]<0 else "flat")
        arrow = "↑" if ac["pct"]>0 else ("↓" if ac["pct"]<0 else "→")
        ac_html = f'<div class="ac-card"><div class="name">中国国航 601111</div><div class="price {c}">{ac["price"]}</div><div class="change {c}">{ac["pct"]:+.2f}% {arrow}</div><div class="detail"><span>最高 {ac["high"]}</span><span>最低 {ac["low"]}</span><span>成交 {ac["amt"]:.0f}万</span></div></div>'

    # 判断
    reasons = ""
    for f in neg: reasons += f"⚠️{f} "
    for f in pos: reasons += f"✅{f} "
    for f in neu: reasons += f"➖{f} "
    v_html = f'<div class="verdict" style="background:{vc}15;border:1px solid {vc}33"><span style="color:{vc}">{v_text}</span><div class="reasons">{reasons}</div></div>' if reasons else ""

    # 核心驱动
    drv_html = '<div class="card"><h3>⚡ 国航的命门</h3>'
    if "WTI原油" in oil_fx:
        w=oil_fx["WTI原油"]; c="up" if w["c"]>0 else "down"
        drv_html+=f'<div class="row"><span class="l">🛢️ WTI原油</span><span class="r {c}">${w["p"]} {w["c"]:+.1f}%</span></div>'
    if "布伦特原油" in oil_fx:
        b=oil_fx["布伦特原油"]; c="up" if b["c"]>0 else "down"
        drv_html+=f'<div class="row"><span class="l">🛢️ 布伦特</span><span class="r {c}">${b["p"]} {b["c"]:+.1f}%</span></div>'
    if "人民币" in oil_fx:
        drv_html+=f'<div class="row"><span class="l">💱 人民币</span><span class="r{"" if oil_fx["人民币"]<7.2 else " up"}">{oil_fx["人民币"]:.4f}</span></div>'
    # 黄金数据已移除
    drv_html+='<div style="font-size:10px;color:#666;margin-top:4px">油价↗=成本↑=利空国航 | 人民币↗=国际收入↑=利好国航</div></div>'

    # 大盘
    idx_html = '<div class="card"><h3>📈 大盘风向</h3>'
    for n in ["上证指数","深证成指","创业板指","恒生指数","道琼斯","纳斯达克"]:
        i=idx.get(n)
        if i:
            c="up" if i["c"]>0 else "down"
            idx_html+=f'<div class="row"><span class="l">{n}</span><span class="r {c}">{i["p"]:.0f} {i["c"]:+.2f}%</span></div>'
    # 市场温度
    if up+down>0:
        idx_html+=f'<div style="margin-top:4px;font-size:10px;color:#666">涨{up}家 跌{down}家 涨停{lu} 跌停{ld}'
        if north is not None: idx_html+=f' | 北向{north:+.0f}亿'
        idx_html+='</div>'
    idx_html+='</div>'

    # 新闻 + 影响分析
    def impact_tag(text):
        """分析新闻对国航的影响"""
        pos_kw = ["油价跌","油价降","原油跌","增产","缓和","解除制裁","协议达成","人民币升","升值","降息","复苏","恢复","增长","利好","新增航线","增开","免签","旅游复苏","游客","出行热"]
        neg_kw = ["油价涨","油价升","原油涨","减产","制裁","冲突","战争","紧张","升级","关闭领空","停飞","取消航班","事故","坠","人民币贬","贬值","加息","加税","关税","贸易战","衰退"]
        for kw in pos_kw:
            if kw in text: return ("利好","#27ae60")
        for kw in neg_kw:
            if kw in text: return ("利空","#e74c3c")
        # 间接判断
        if any(k in text for k in ["美国","伊朗","中东","石油","原油","OPEC","霍尔木兹"]):
            return ("关注","#e67e22")
        if any(k in text for k in ["涨","新高","反弹","突破"]):
            return ("偏多","#3498db")
        if any(k in text for k in ["跌","新低","崩","暴跌","恐慌"]):
            return ("偏空","#95a5a6")
        return ("","")

    news_html = ""
    for cat,items in news.items():
        if not items: continue
        news_html+=f'<div class="card"><h3>{cat}</h3>'
        for n in items[:4]:
            tag, tc = impact_tag(n)
            tag_html = f' <span style="font-size:9px;padding:1px 5px;border-radius:3px;background:{tc}18;color:{tc};border:1px solid {tc}33">{tag}</span>' if tag else ""
            news_html+=f'<div class="news-item">▸ {n}{tag_html}</div>'
        news_html+='</div>'

    ft = '<div class="footer">⚠️ 仅供参考 · 每天9:00/20:00推送<br>油价决定成本 · 汇率决定收入 · 局势决定风险</div>'

    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{ac_html}{v_html}{drv_html}{idx_html}{news_html}{ft}</body></html>'

def main():
    print("⏳ 采集...")
    ac = get_airchina(); print(f"  国航: {'OK' if ac else 'N/A'}")
    oil_fx = get_oil_fx_gold(); print(f"  命门: {list(oil_fx.keys())}")
    idx = get_index(); print(f"  指数: {list(idx.keys())}")
    up,down,lu,ld = get_breadth(); print(f"  涨跌: {up}/{down}")
    north = get_north(); print(f"  北向: {north}")
    items = get_news(); print(f"  新闻: {len(items)}条")
    news = filter_for_airchina(items)
    for k,v in news.items(): print(f"    {k}: {len(v)}")

    neg,pos,neu = analyze(ac, oil_fx, idx, up,down,lu,ld, north, news)
    html = build(ac, oil_fx, idx, up,down,lu,ld, north, news, neg,pos,neu)
    now = datetime.now(BEIJING_TZ)
    emoji = "🌅" if now.hour<12 else "🌙"
    push(f"{emoji} 国航 · {now.strftime('%m/%d %H:%M')}", html)

if __name__=="__main__":
    main()
