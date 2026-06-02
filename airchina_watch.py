#!/usr/bin/env python3
"""国航盯盘 - 每天9:00/20:00推送"""
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

def sina(s):
    import urllib.request as ur
    req = ur.Request(f"https://hq.sinajs.cn/list={s}",headers={"Referer":"https://finance.sina.com.cn"})
    return ur.urlopen(req,timeout=10).read().decode("gbk").split('"')[1].split(",")

# ====== 数据 ======

def get_airchina():
    try:
        d = sina("sh601111"); p = float(d[3]); pv = float(d[2])
        return {"price":p,"prev":pv,"pct":round((p-pv)/pv*100,2),"high":float(d[4]),"low":float(d[5]),"amt":round(float(d[9])/10000,0)}
    except: return None

def get_oil_fx():
    r = {}
    import akshare as ak
    for s,n in [("CL","WTI"),("B","布伦特")]:
        try:
            df = ak.futures_foreign_hist(symbol=s)
            l,p = df.iloc[-1],df.iloc[-2]
            r[n] = {"p":round(l["close"],2),"c":round((l["close"]-p["close"])/p["close"]*100,2)}
        except: pass
    try: r["人民币"] = float(sina("USDCNY")[1])
    except: pass
    return r

def get_index():
    import akshare as ak
    idx = {}
    for c,n in [("sh000001","上证"),("sz399001","深证"),("sz399006","创业板")]:
        try:
            df = ak.stock_zh_index_daily(symbol=c)
            l = df.iloc[-1]
            idx[n] = {"p":round(l["close"],2),"c":round((l["close"]-l["open"])/l["open"]*100,2)}
        except: pass
    for code,name in [("hkHSI","恒生"),(".DJI","道琼斯"),(".IXIC","纳斯达克")]:
        try:
            d = sina(code)
            idx[name] = {"p":round(float(d[1]),2),"c":round(float(d[3] if code.startswith("hk") else d[2]),2)}
        except: pass
    return idx

def get_news():
    """新浪财经 - 只取最新"""
    import urllib.request as ur, json as j, time
    items = []
    now = time.time()
    for lid in [2509,2510,2512]:
        try:
            url = f'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid={lid}&k=&num=20&page=1'
            req = ur.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
            data = j.loads(ur.urlopen(req,timeout=10).read().decode())
            for item in data.get('result',{}).get('data',[]):
                ctime = int(item.get('ctime',0))
                if now - ctime > 86400: continue  # 只要24小时内
                t = item.get('title','') or item.get('intro','')
                if t and 10<len(t)<200: items.append(t)
        except: pass
    seen=set(); uniq=[]
    for i in items:
        k=i[:40]
        if k not in seen: seen.add(k); uniq.append(i)
    return uniq

def classify(news_list):
    """分类 + 只保留相关新闻"""
    cats = {
        "✈️ 航空出行": ["国航","航空","机票","航班","机场","波音","空客","免签","签证","出境游","入境游","旅游","航线","东航","南航"],
        "🛢️ 原油能源": ["原油","油价","OPEC","石油","减产","产油","能源","燃油"],
        "🔥 中东局势": ["伊朗","中东","波斯湾","以色列","沙特","霍尔木兹","也门","胡塞"],
        "💱 汇率贸易": ["人民币","汇率","关税","贸易战","中美","脱钩","制裁"],
        "🏛️ 宏观政策": ["美联储","央行","降息","降准","加息","利率","CPI","通胀","GDP","PMI","政治局","国常会","LPR"],
        "📊 市场动态": ["A股","大盘","暴涨","暴跌","北向","新高","新低","恐慌","美股","纳指","道指","标普"],
        "🌍 国际政治": ["特朗普","拜登","大选","白宫","北约","乌克兰","俄罗斯","台海","南海","朝鲜"],
    }
    result = {}; used = set()
    skip = ["足球","球员","大名单","世界杯","联赛","NBA","演唱会","综艺","八卦","游戏","AI","芯片","SpaceX","IPO","记者协会"]
    for cat,kws in cats.items():
        m = []
        for n in news_list:
            if id(n) in used: continue
            if any(s in n for s in skip): continue
            if any(k in n for k in kws):
                m.append(n); used.add(id(n))
                if len(m) >= 4: break
        if m: result[cat] = m
    return result

def analyze_one(text):
    """单条新闻影响分析"""
    t = text
    # 按优先级从高到低
    tests = [
        (lambda: ("🔴 利空","油价上涨→航空燃油成本↑→压缩利润","#e74c3c"), lambda: ("油价涨"in t or "油价升"in t or "原油涨"in t) and "跌" not in t),
        (lambda: ("🟢 利好","油价下跌→燃油成本↓→利润率提升","#27ae60"), lambda: "油价跌"in t or "油价降"in t or "原油跌"in t),
        (lambda: ("🔴 利空","中东局势紧张→原油供应风险→油价上行→航空成本↑","#e74c3c"), lambda: ("伊朗"in t or "中东"in t) and ("冲突"in t or "紧张"in t or "升级"in t or "制裁"in t)),
        (lambda: ("🟢 利好","美伊关系缓和→原油供应风险↓→成本端利好","#27ae60"), lambda: ("伊朗"in t or "美伊"in t) and ("缓和"in t or "协议"in t or "对话"in t or "谈判"in t)),
        (lambda: ("🟢 利好","人民币升值→国际航线收入↑","#27ae60"), lambda: "人民币升"in t or "人民币走强"in t),
        (lambda: ("🔴 利空","人民币贬值→国际收入缩水→成本↑","#e74c3c"), lambda: "人民币贬"in t or "人民币走弱"in t),
        (lambda: ("🟢 利好","美联储降息→美元走弱→人民币相对升值","#27ae60"), lambda: ("降息"in t or "美联储"in t+"降"in t) and "英"not in t and "欧"not in t),
        (lambda: ("🔴 利空","加息→美元走强→人民币贬值压力","#e74c3c"), lambda: "加息"in t and "英"not in t and "欧"not in t),
        (lambda: ("🟢 利好","免签/签证便利→出境游↑→国际航线客流↑","#27ae60"), lambda: "免签"in t or ("签证"in t and "便利"in t)),
        (lambda: ("🟢 利好","航线增加→国航运力扩张→收入预期↑","#27ae60"), lambda: ("航线"in t or "航班"in t) and ("增"in t or "恢复"in t or "新开"in t)),
        (lambda: ("🔴 利空","航班运营受阻→国航收入直接受损","#e74c3c"), lambda: "停飞"in t or "取消航班"in t or "关闭领空"in t),
        (lambda: ("🟢 利好","贸易缓和→经济信心↑→出行需求↑","#27ae60"), lambda: ("关税"in t or "贸易"in t) and ("缓和"in t or "续期"in t or "协议"in t or "延长"in t)),
        (lambda: ("🔴 利空","贸易摩擦升级→全球经济承压→商务出行↓","#e74c3c"), lambda: ("关税"in t or "贸易"in t) and ("加"in t or "升级"in t or "新增"in t)),
        (lambda: ("🟢 利好","市场高涨→风险偏好↑→航空股估值提升","#27ae60"), lambda: "暴涨"in t or "大涨"in t or "创新高"in t),
        (lambda: ("🔴 利空","市场恐慌→系统性风险→航空股被错杀","#e74c3c"), lambda: "暴跌"in t or "崩盘"in t or "恐慌"in t),
        (lambda: ("🔴 利空","地缘冲突→不稳定→出行↓+油价风险","#e74c3c"), lambda: "战争"in t or "军事冲突"in t),
        (lambda: ("🟠 关注","涉及影响国航核心变量，需持续跟踪","#e67e22"), lambda: "特朗普"in t and ("伊朗"in t or "关税"in t or "制裁"in t or "贸易"in t)),
    ]
    for result_fn, condition_fn in tests:
        if condition_fn():
            return result_fn()
    return ("","","")

def analyze(ac, oil, idx, news):
    neg, pos, neu = [], [], []
    if ac:
        p = ac["pct"]
        if p < -5: neg.append(f"国航大跌{abs(p)}%")
        elif p < -3: neg.append(f"国航跌{abs(p)}%")
        elif p > 5: pos.append(f"国航大涨{p}%")
        elif p > 3: pos.append(f"国航涨{p}%")
    wti = oil.get("WTI",{}).get("c",0)
    if wti > 3: neg.append(f"WTI涨{wti:.1f}%→成本↑")
    elif wti < -3: pos.append(f"WTI跌{abs(wti):.1f}%→成本↓")
    elif wti > 1: neu.append(f"油价微涨{wti:.1f}%")
    elif wti < -1: neu.append(f"油价微跌{abs(wti):.1f}%")
    cny = oil.get("人民币",7.2)
    if cny > 7.3: neg.append(f"人民币{cny}→收入↓")
    elif cny < 7.0: pos.append(f"人民币{cny}→收入↑")
    return neg, pos, neu

def verdict(neg, pos, ac):
    n, p = len(neg), len(pos)
    acp = ac.get("pct",0) if ac else 0
    if acp <= -3: return f"🔴 国航跌{abs(acp)}%","#e74c3c"
    if acp <= -1: return "🟠 国航走弱","#e67e22"
    if acp >= 3: return f"🟢 国航涨{acp}%","#27ae60"
    if acp >= 1: return "🔵 国航走强","#3498db"
    if n >= 3: return "🔴 利空叠加","#e74c3c"
    if n >= 1: return "🟠 注意风险","#e67e22"
    if p >= 3: return "🟢 利好共振","#27ae60"
    if p >= 1: return "🔵 偏积极","#3498db"
    return "⚪ 中性","#95a5a6"

# ====== 构建推送 ======
def build(ac, oil, idx, news, neg, pos, neu):
    now = datetime.now(BEIJING_TZ); ds = now.strftime("%m/%d %H:%M")
    emoji = "🌅" if now.hour < 12 else "🌙"
    v_text, vc = verdict(neg, pos, ac)

    css = """*{margin:0;padding:0}body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f6f8;color:#2c3e50;padding:12px;font-size:14px}
.hd{text-align:center;padding:16px 0 12px;margin-bottom:10px}
.hd h1{font-size:17px;color:#1a1a2e;font-weight:700}.hd .t{font-size:11px;color:#95a5a6;margin-top:3px}
.ac{background:#fff;border-radius:10px;padding:16px;margin-bottom:10px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.06)}
.ac .n{font-size:12px;color:#95a5a6;letter-spacing:1px}.ac .p{font-size:32px;font-weight:700;margin:4px 0;color:#1a1a2e}.ac .c{font-size:14px;font-weight:600}
.ac .d{display:flex;justify-content:center;gap:16px;margin-top:6px;font-size:11px;color:#b0b0b0}
.ac .d span{background:#f8f9fa;padding:2px 8px;border-radius:4px}
.up{color:#e74c3c}.down{color:#27ae60}
.ve{text-align:center;padding:10px 14px;margin-bottom:10px;border-radius:8px;font-size:14px;font-weight:600;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.04)}
.ve .rs{font-size:11px;margin-top:3px;font-weight:400;opacity:.75}
.card{background:#fff;border-radius:8px;padding:14px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.04)}
.card h3{font-size:13px;color:#1a1a2e;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #eee;font-weight:600}
.row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:13px}
.row .l{color:#7f8c8d}.row .r{text-align:right;font-weight:500;color:#2c3e50}
.news{font-size:12px;padding:5px 0;border-bottom:1px solid #f0f0f0;line-height:1.6;color:#444}
.news:last-child{border-bottom:none}
.tag{font-size:10px;padding:2px 8px;border-radius:4px;margin-top:3px;display:inline-block;line-height:1.5}
.ft{text-align:center;font-size:11px;color:#bdc3c7;padding:12px;line-height:1.6}"""

    hdr = f'<div class="hd"><h1>✈️ 国航盯盘</h1><div class="t">{ds} 北京 · 每天9:00/20:00自动推送</div></div>'

    ac_html = ""
    if ac:
        c = "up" if ac["pct"]>0 else "down"
        arrow = "↑" if ac["pct"]>0 else "↓"
        ac_html = f'<div class="ac"><div class="n">中国国航 601111</div><div class="p {c}">{ac["price"]}</div><div class="c {c}">{ac["pct"]:+.2f}% {arrow}</div><div class="d"><span>最高{ac["high"]}</span><span>最低{ac["low"]}</span><span>成交{ac["amt"]:.0f}万</span></div></div>'

    reasons = " ".join([f"⚠️{f}" for f in neg] + [f"✅{f}" for f in pos] + [f"➖{f}" for f in neu])
    v_html = f'<div class="ve" style="background:{vc}15;border:1px solid {vc}33"><span style="color:{vc}">{v_text}</span><div class="rs">{reasons}</div></div>' if reasons else ""

    drv = '<div class="card"><h3>⚡ 关键指标  <span style="font-size:10px;color:#e94560">油价↗利空 | 人民币↗利好</span></h3>'
    if "WTI" in oil:
        w=oil["WTI"]; c="up" if w["c"]>0 else "down"
        drv += f'<div class="row"><span class="l">🛢️ WTI原油</span><span class="r {c}">${w["p"]} {w["c"]:+.1f}%</span></div>'
    if "布伦特" in oil:
        b=oil["布伦特"]; c="up" if b["c"]>0 else "down"
        drv += f'<div class="row"><span class="l">🛢️ 布伦特</span><span class="r {c}">${b["p"]} {b["c"]:+.1f}%</span></div>'
    if "人民币" in oil:
        drv += f'<div class="row"><span class="l">💱 人民币</span><span class="r">{oil["人民币"]:.4f}</span></div>'
    drv += '</div>'

    idx_h = '<div class="card"><h3>📈 大盘风向</h3>'
    for n in ["上证","深证","创业板","恒生","道琼斯","纳斯达克"]:
        i=idx.get(n)
        if i:
            c="up" if i["c"]>0 else "down"
            idx_h+=f'<div class="row"><span class="l">{n}</span><span class="r {c}">{i["p"]:.0f} {i["c"]:+.2f}%</span></div>'
    idx_h += '</div>'

    news_h = ""
    for cat,items in news.items():
        if not items: continue
        news_h += f'<div class="card"><h3>{cat}</h3>'
        for n in items[:4]:
            tag, detail, tc = analyze_one(n)
            if detail:
                news_h += f'<div class="news">▸ {n}<br><span class="tag" style="background:{tc}18;color:{tc};border:1px solid {tc}44">{detail}</span></div>'
            else:
                news_h += f'<div class="news">▸ {n}</div>'
        news_h += '</div>'

    ft = '<div class="ft">⚠️ 仅供参考 · 腾讯云24h运行<br>油价决定成本 · 汇率决定收入 · 局势决定风险</div>'

    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{hdr}{ac_html}{v_html}{drv}{idx_h}{news_h}{ft}</body></html>'

def main():
    print("⏳ 采集...")
    ac = get_airchina(); print(f"  国航: {'OK' if ac else 'N/A'}")
    oil = get_oil_fx(); print(f"  驱动: {list(oil.keys())}")
    idx = get_index(); print(f"  指数: {len(idx)}项")
    items = get_news(); print(f"  新闻: {len(items)}条")
    news = classify(items)
    for k,v in news.items():
        tagged = sum(1 for n in v if analyze_one(n)[0])
        print(f"    {k}: {len(v)}条 (含分析{tagged})")
    neg, pos, neu = analyze(ac, oil, idx, news)
    html = build(ac, oil, idx, news, neg, pos, neu)
    now = datetime.now(BEIJING_TZ)
    emoji = "🌅" if now.hour < 12 else "🌙"
    push(f"{emoji} 国航盯盘 · {now.strftime('%m/%d %H:%M')}", html)

if __name__ == "__main__":
    main()
