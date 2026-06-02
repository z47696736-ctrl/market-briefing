#!/bin/bash
# 一键部署脚本 - 市场简报

echo "=== 安装依赖 ==="
sudo apt update -y
sudo apt install python3-pip -y
pip3 install akshare

echo "=== 创建脚本 ==="
mkdir -p /home/ubuntu/briefing
cat > /home/ubuntu/briefing/market_briefing.py << 'PYEOF'
#!/usr/bin/env python3
"""
每日市场简报 —— 定时推送到手机微信
"""
from datetime import datetime, timezone, timedelta
import json, os, urllib.request

BEIJING_TZ = timezone(timedelta(hours=8))

def get_token():
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if token:
        return token
    cf = "/home/ubuntu/briefing/config.json"
    if os.path.exists(cf):
        with open(cf) as f:
            t = json.load(f).get("pushplus_token", "")
            if t and t != "你的Token填这里":
                return t
    return ""

def push_to_phone(title, content):
    token = get_token()
    if not token:
        print("⚠️ 未设置 PUSHPLUS_TOKEN")
        return
    try:
        data = json.dumps({"token": token, "title": title, "content": content, "template": "html"}).encode()
        req = urllib.request.Request("https://www.pushplus.plus/send", data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get("code") == 200:
            print("📲 已推送到手机微信！")
        else:
            print(f"⚠️ 推送失败: {result.get('msg')}")
    except Exception as e:
        print(f"⚠️ 推送异常: {e}")

def get_a_share_snapshot():
    try:
        import akshare as ak
        codes = ["sh000001","sz399001","sz399006","sh000300"]
        names = ["上证指数","深证成指","创业板指","沪深300"]
        result = []
        for code, name in zip(codes, names):
            df = ak.stock_zh_index_daily(symbol=code)
            latest = df.iloc[-1]
            change_pct = round((latest["close"] - latest["open"]) / latest["open"] * 100, 2)
            result.append({"name": name, "close": round(latest["close"], 2), "change_pct": change_pct})
        return result
    except Exception as e:
        return [{"error": str(e)}]

def get_a_share_news():
    try:
        import akshare as ak
        news_list = []
        try:
            news_df = ak.stock_news_em()
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(10).iterrows():
                    t = row.get("title", "")
                    if t:
                        news_list.append(str(t))
        except:
            pass
        return news_list if news_list else ["(暂无)"]
    except:
        return ["(新闻获取失败)"]

def get_us_market():
    result = []
    try:
        import akshare as ak
        for sym, nm in [(".DJI","道琼斯"),(".IXIC","纳斯达克"),(".INX","标普500")]:
            try:
                df = ak.index_us_stock_sina(symbol=sym)
                latest = df.iloc[-1]
                result.append({"name": nm, "close": round(latest["close"],2), "change_pct": round(float(latest.get("change_pct",0)),2)})
            except:
                result.append({"name": nm, "note": "N/A"})
    except:
        pass
    return result

def get_oil():
    result = []
    try:
        import akshare as ak
        for sym, nm in [("WTI原油","WTI原油"),("布伦特原油","布伦特原油")]:
            try:
                df = ak.futures_foreign_hist(symbol=sym)
                l,p = df.iloc[-1], df.iloc[-2]
                ch = round((l["close"]-p["close"])/p["close"]*100,2)
                result.append({"name": nm, "price": round(l["close"],2), "change_pct": ch})
            except:
                result.append({"name": nm, "note": "N/A"})
    except:
        pass
    return result

def get_air_china():
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="601111", period="daily", adjust="qfq")
        l, p = df.iloc[-1], df.iloc[-2]
        ch = round((l["收盘"]-p["收盘"])/p["收盘"]*100,2)
        return {"name":"中国国航","close":round(l["收盘"],2),"change_pct":ch}
    except:
        return {"name":"中国国航","note":"N/A"}

def get_me_news():
    kw = ["伊朗","美国","中东","美伊","原油","油价","OPEC","制裁","以色列","波斯湾"]
    nl = []
    try:
        import akshare as ak
        try:
            df = ak.stock_news_em()
            if df is not None and not df.empty:
                for _, row in df.head(30).iterrows():
                    t = str(row.get("title",""))
                    if any(k in t for k in kw):
                        nl.append(t)
                        if len(nl) >= 5:
                            break
        except:
            pass
    except:
        pass
    return nl

def is_morning():
    return datetime.now(BEIJING_TZ).hour < 12

def build_content(ash, news, us, oil, ac, me):
    def c(pct):
        if isinstance(pct,(int,float)):
            return f'<span style="color:red">+{pct}%</span>' if pct>0 else (f'<span style="color:green">{pct}%</span>' if pct<0 else '0.00%')
        return str(pct)

    ra = "".join(f"<tr><td>{i['name']}</td><td>{i['close']}</td><td>{c(i['change_pct'])}</td></tr>" for i in ash if "close" in i)
    ru = "".join(f"<tr><td>{i['name']}</td><td>{i['close']}</td><td>{c(i['change_pct'])}</td></tr>" for i in us if "close" in i)

    if is_morning():
        ts = f"<h3>🇺🇸 隔夜美股</h3><table border='1' cellpadding='4'>{ru}</table>"
        ms = f"<h3>🇨🇳 A股盘前</h3><table border='1' cellpadding='4'>{ra}</table>"
    else:
        ts = f"<h3>🇨🇳 A股收盘</h3><table border='1' cellpadding='4'>{ra}</table>"
        ms = f"<h3>🇺🇸 美股</h3><table border='1' cellpadding='4'>{ru}</table>"

    if "close" in ac:
        ach = f"<p><b>✈️ 中国国航 601111:</b> {ac['close']}元 {c(ac['change_pct'])}</p>"
    else:
        ach = "<p>✈️ 中国国航: N/A</p>"

    or_ = "".join(f"<tr><td>{i['name']}</td><td>${i['price']}</td><td>{c(i['change_pct'])}</td></tr>" for i in oil if "price" in i)
    oh = f"<h3>🛢️ 原油（油价↗=利空航空）</h3><table border='1' cellpadding='4'>{or_}</table>"

    mh = ""
    if me:
        mh = "<h3>🔥 美伊/中东局势</h3><ul>" + "".join(f"<li>{n}</li>" for n in me[:5]) + "</ul>"

    nl = "".join(f"<li>{n}</li>" for n in news[:6])

    return f"""{ach}{oh}{mh}{ts}{ms}<h3>📰 热点新闻</h3><ul>{nl}</ul><p style='color:#999;font-size:12px'>⚠️ 仅供参考</p>"""

def main():
    print("⏳ 抓取中...")
    now = datetime.now(BEIJING_TZ)
    ds = now.strftime("%Y年%m月%d日 %H:%M")
    bt = "🌅 盘前简报" if is_morning() else "🌙 收盘简报"

    ash = get_a_share_snapshot()
    news = get_a_share_news()
    us = get_us_market()
    oil = get_oil()
    ac = get_air_china()
    me = get_me_news()

    content = build_content(ash, news, us, oil, ac, me)
    push_to_phone(f"📊 {bt} - {ds}", content)

if __name__ == "__main__":
    main()
PYEOF

chmod +x /home/ubuntu/briefing/market_briefing.py

echo ""
echo "=== 设置 PushPlus Token ==="
read -p "请输入你的 PushPlus Token: " pptoken
echo "{\"pushplus_token\": \"$pptoken\"}" > /home/ubuntu/briefing/config.json

echo ""
echo "=== 设置定时任务 ==="
# 早9点 晚20点 (北京时间)
(crontab -l 2>/dev/null; echo "0 9 * * * cd /home/ubuntu/briefing && python3 market_briefing.py >> /home/ubuntu/briefing/cron.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "0 20 * * * cd /home/ubuntu/briefing && python3 market_briefing.py >> /home/ubuntu/briefing/cron.log 2>&1") | crontab -

echo ""
echo "=== 部署完成 ==="
echo "定时任务: 每天 9:00 和 20:00 自动推送"
echo "手动测试: cd /home/ubuntu/briefing && python3 market_briefing.py"
echo "查看日志: cat /home/ubuntu/briefing/cron.log"
echo ""
echo "推送Token: $pptoken"
