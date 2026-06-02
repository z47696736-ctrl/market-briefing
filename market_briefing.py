"""
每日市场简报 —— 云端自动推送到手机微信
适配：本地运行 + GitHub Actions 云端运行
"""
from datetime import datetime, timezone, timedelta
import json
import os
import urllib.request


# ==================== 配置 ====================

# 北京时间
BEIJING_TZ = timezone(timedelta(hours=8))

def get_token():
    """获取 PushPlus Token：优先环境变量，否则读 config.json"""
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if token:
        return token
    # 本地运行时的兼容方案
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            token = config.get("pushplus_token", "")
            if token and token != "你的Token填这里":
                return token
    return ""


# ==================== PushPlus 推送 ====================

def push_to_phone(title, content):
    """通过 PushPlus 推送到手机微信"""
    token = get_token()
    if not token:
        print("⚠️ 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    try:
        data = json.dumps({
            "token": token,
            "title": title,
            "content": content,
            "template": "html"
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://www.pushplus.plus/send",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get("code") == 200:
            print("📲 已推送到手机微信！")
        else:
            print(f"⚠️ 推送失败: {result.get('msg', '未知错误')}")
    except Exception as e:
        print(f"⚠️ 推送异常: {e}")


# ==================== 数据获取 ====================

def get_a_share_snapshot():
    """获取 A 股主要指数行情"""
    try:
        import akshare as ak
        codes = ["sh000001", "sz399001", "sz399006", "sh000300"]
        names = ["上证指数", "深证成指", "创业板指", "沪深300"]
        result = []
        for code, name in zip(codes, names):
            df = ak.stock_zh_index_daily(symbol=code)
            latest = df.iloc[-1]
            change_pct = round((latest["close"] - latest["open"]) / latest["open"] * 100, 2)
            result.append({
                "name": name,
                "close": round(latest["close"], 2),
                "change_pct": change_pct,
            })
        return result
    except Exception as e:
        return [{"error": f"A股数据获取失败: {e}"}]


def get_a_share_news():
    """获取 A 股重大新闻"""
    try:
        import akshare as ak
        news_list = []
        try:
            news_df = ak.stock_news_em()
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(10).iterrows():
                    title = row.get("title", "")
                    if title:
                        news_list.append(str(title))
        except Exception:
            pass
        return news_list if news_list else ["(今日暂无重大新闻)"]
    except Exception as e:
        return [f"新闻获取失败: {e}"]


def get_us_market_snapshot():
    """获取美股主要指数"""
    result = []
    try:
        import akshare as ak
        for symbol, name in [(".DJI", "道琼斯"), (".IXIC", "纳斯达克"), (".INX", "标普500")]:
            try:
                df = ak.index_us_stock_sina(symbol=symbol)
                latest = df.iloc[-1]
                result.append({
                    "name": name,
                    "close": round(latest["close"], 2),
                    "change_pct": round(float(latest.get("change_pct", 0)), 2),
                })
            except Exception:
                result.append({"name": name, "note": "数据暂不可用"})
    except Exception as e:
        return [{"error": f"美股数据获取失败: {e}"}]
    return result


def get_oil_price():
    """获取原油价格（美伊局势核心指标）"""
    try:
        import akshare as ak
        result = []
        # WTI 原油
        try:
            df_wti = ak.futures_foreign_hist(symbol="WTI原油")
            latest = df_wti.iloc[-1]
            prev = df_wti.iloc[-2]
            change = round((latest["close"] - prev["close"]) / prev["close"] * 100, 2)
            result.append({"name": "WTI原油", "price": round(latest["close"], 2), "change_pct": change})
        except Exception:
            result.append({"name": "WTI原油", "note": "数据暂不可用"})
        # 布伦特原油
        try:
            df_brent = ak.futures_foreign_hist(symbol="布伦特原油")
            latest = df_brent.iloc[-1]
            prev = df_brent.iloc[-2]
            change = round((latest["close"] - prev["close"]) / prev["close"] * 100, 2)
            result.append({"name": "布伦特原油", "price": round(latest["close"], 2), "change_pct": change})
        except Exception:
            result.append({"name": "布伦特原油", "note": "数据暂不可用"})
        return result
    except Exception:
        return [{"name": "原油", "note": "数据获取失败"}]


def get_air_china_stock():
    """获取中国国航 601111 行情"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="601111", period="daily", adjust="qfq")
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        change_pct = round((latest["收盘"] - prev["收盘"]) / prev["收盘"] * 100, 2)
        return {
            "name": "中国国航",
            "code": "601111",
            "close": round(latest["收盘"], 2),
            "change_pct": change_pct,
            "volume": int(latest.get("成交量", 0)),
        }
    except Exception:
        return {"name": "中国国航", "note": "数据暂不可用"}


def get_middle_east_news():
    """获取美伊/中东局势相关新闻"""
    keywords = ["伊朗", "美国", "中东", "美伊", "原油", "油价", "OPEC", "欧佩克", "波斯湾", "霍尔木兹", "以色列", "制裁"]
    news_list = []
    try:
        import akshare as ak
        try:
            news_df = ak.stock_news_em()
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(30).iterrows():
                    title = str(row.get("title", ""))
                    if any(kw in title for kw in keywords):
                        news_list.append(title)
                        if len(news_list) >= 5:
                            break
        except Exception:
            pass
    except Exception:
        pass
    return news_list


def get_a_share_news():
    """获取全球宏观要闻"""
    news_list = []
    try:
        import akshare as ak
        try:
            macro_df = ak.news_economic_baidu()
            if macro_df is not None and not macro_df.empty:
                for _, row in macro_df.head(5).iterrows():
                    title = row.get("title", "")
                    if title:
                        news_list.append(str(title))
        except Exception:
            pass
    except Exception:
        pass
    return news_list if news_list else []


# ==================== 格式化输出 ====================

def colorize(pct):
    if isinstance(pct, (int, float)):
        return f"+{pct}%" if pct > 0 else (f"{pct}%" if pct < 0 else "0.00%")
    return str(pct)


def is_morning():
    """判断当前是否是早间简报（9点附近）"""
    now = datetime.now(BEIJING_TZ)
    return now.hour < 12


def print_report(date_str, a_share, a_news, us_market, global_news, oil, air_china, me_news):
    """在终端打印报告"""
    briefing_type = "🌅 盘前简报" if is_morning() else "🌙 收盘简报"
    
    print()
    print("╔══════════════════════════════════════════╗")
    print(f"║        📊 每 日 市 场 简 报               ║")
    print(f"║        {briefing_type}                    ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  {date_str}                     ║")
    print("╚══════════════════════════════════════════╝")

    # A 股
    print("\n┌── 🇨🇳 A 股主要指数 ──────────────────────────┐")
    print(f"│ {'指数':12s} {'收盘':>10s}  {'涨跌幅':>10s} │")
    print("├──────────────────────────────────────────────┤")
    for item in a_share:
        if "error" in item:
            print(f"│ ⚠ {item['error'][:40]} │")
        elif "note" in item:
            print(f"│ {item.get('name', ''):12s} {'—':>10s}  {'数据暂不可用':>10s} │")
        else:
            sign = "🔴" if item.get("change_pct", 0) > 0 else ("🟢" if item.get("change_pct", 0) < 0 else "⚪")
            print(f"│ {sign} {item['name']:10s} {item['close']:>10.2f}  {colorize(item['change_pct']):>10s} │")
    print("└──────────────────────────────────────────────┘")

    # 美股
    print("\n┌── 🇺🇸 美股主要指数 ──────────────────────────┐")
    print(f"│ {'指数':12s} {'收盘':>10s}  {'涨跌幅':>10s} │")
    print("├──────────────────────────────────────────────┤")
    for item in us_market:
        if "error" in item:
            print(f"│ ⚠ {item['error'][:40]} │")
        elif "note" in item:
            print(f"│ {item.get('name', ''):12s} {'—':>10s}  {'数据暂不可用':>10s} │")
        else:
            sign = "🔴" if item.get("change_pct", 0) > 0 else ("🟢" if item.get("change_pct", 0) < 0 else "⚪")
            print(f"│ {sign} {item['name']:10s} {item['close']:>10.2f}  {colorize(item['change_pct']):>10s} │")
    print("└──────────────────────────────────────────────┘")

    # A 股新闻
    if a_news:
        print(f"\n┌── 📰 A 股重大新闻 ───────────────────────────┐")
        for i, news in enumerate(a_news[:8], 1):
            title = news if len(news) <= 40 else news[:38] + ".."
            print(f"│ {i}. {title}")
        print("└──────────────────────────────────────────────┘")

    # 全球新闻
    if global_news:
        print(f"\n┌── 🌍 全球宏观要闻 ───────────────────────────┐")
        for i, news in enumerate(global_news[:5], 1):
            title = news if len(news) <= 40 else news[:38] + ".."
            print(f"│ {i}. {title}")
        print("└──────────────────────────────────────────────┘")

    # 中国国航
    print(f"\n┌── ✈️ 中国国航 601111 ─────────────────────────┐")
    if "close" in air_china:
        sign = "🔴" if air_china.get("change_pct", 0) > 0 else ("🟢" if air_china.get("change_pct", 0) < 0 else "⚪")
        print(f"│ 收盘: {air_china['close']}  {sign} {colorize(air_china['change_pct'])}")
    else:
        print(f"│ {air_china.get('note', '数据暂不可用')}")
    print("└──────────────────────────────────────────────┘")

    # 原油（美伊局势核心）
    print(f"\n┌── 🛢️ 原油价格（油价↗ = 利空航空）─────────────┐")
    for item in oil:
        if "price" in item:
            sign = "🔴" if item.get("change_pct", 0) > 0 else ("🟢" if item.get("change_pct", 0) < 0 else "⚪")
            print(f"│ {item['name']}: ${item['price']}  {sign} {colorize(item['change_pct'])}")
        else:
            print(f"│ {item.get('name', '')} {item.get('note', '')}")
    print("└──────────────────────────────────────────────┘")

    # 美伊/中东局势
    if me_news:
        print(f"\n┌── 🔥 美伊/中东局势 ───────────────────────────┐")
        for i, news in enumerate(me_news[:5], 1):
            title = news if len(news) <= 40 else news[:38] + ".."
            print(f"│ {i}. {title}")
        print("└──────────────────────────────────────────────┘")

    print("\n⚠️  数据来源公开接口，仅供参考，不构成投资建议。")


# ==================== 推送内容构建 ====================

def build_push_content(a_share, a_news, us_market, global_news, oil, air_china, me_news):
    """构建推送用的简洁 HTML"""
    def c(pct):
        if isinstance(pct, (int, float)):
            if pct > 0: return f'<span style="color:red">+{pct}%</span>'
            if pct < 0: return f'<span style="color:green">{pct}%</span>'
        return str(pct) if not isinstance(pct, str) else pct

    rows_a = "".join(
        f"<tr><td>{item['name']}</td><td>{item['close']}</td><td>{c(item['change_pct'])}</td></tr>"
        for item in a_share if "close" in item
    )
    rows_us = "".join(
        f"<tr><td>{item['name']}</td><td>{item['close']}</td><td>{c(item['change_pct'])}</td></tr>"
        for item in us_market if "close" in item
    )

    # 早间：美股放前面（隔夜影响大）；晚间：A股放前面
    if is_morning():
        top_section = f"<h3>🇺🇸 隔夜美股收盘</h3><table border='1' cellpadding='4' cellspacing='0'>{rows_us}</table>"
        middle_section = f"<h3>🇨🇳 A股盘前</h3><table border='1' cellpadding='4' cellspacing='0'>{rows_a}</table>"
    else:
        top_section = f"<h3>🇨🇳 A股收盘</h3><table border='1' cellpadding='4' cellspacing='0'>{rows_a}</table>"
        middle_section = f"<h3>🇺🇸 美股行情</h3><table border='1' cellpadding='4' cellspacing='0'>{rows_us}</table>"

    # 国航
    if "close" in air_china:
        ac_sign = "🔴+" if air_china.get("change_pct", 0) > 0 else ("🟢" if air_china.get("change_pct", 0) < 0 else "⚪")
        air_china_html = f"<p><b>✈️ 中国国航 601111:</b> {air_china['close']}元 {ac_sign}{air_china['change_pct']}%</p>"
    else:
        air_china_html = "<p>✈️ 中国国航: 数据暂不可用</p>"

    # 原油
    oil_rows = "".join(
        f"<tr><td>{item['name']}</td><td>${item['price']}</td><td style='color:{'red' if item.get('change_pct', 0) > 0 else 'green'}'>{'+' if item.get('change_pct', 0) > 0 else ''}{item.get('change_pct', '?')}%</td></tr>"
        for item in oil if "price" in item
    )
    oil_html = f"<h3>🛢️ 原油价格（油价↗ = 利空航空）</h3><table border='1' cellpadding='4' cellspacing='0'><tr><th>品种</th><th>价格</th><th>涨跌</th></tr>{oil_rows}</table>"

    # 美伊局势
    me_html = ""
    if me_news:
        me_li = "".join(f"<li>{n}</li>" for n in me_news[:5])
        me_html = f"<h3>🔥 美伊/中东局势</h3><ul>{me_li}</ul>"

    news_li = "".join(f"<li>{n}</li>" for n in a_news[:6])
    global_li = "".join(f"<li>{n}</li>" for n in global_news[:4])

    return f"""{air_china_html}
{oil_html}
{me_html}
{top_section}
{middle_section}
<h3>📰 市场热点新闻</h3><ul>{news_li}</ul>
<h3>🌍 全球宏观要闻</h3><ul>{global_li}</ul>
<p style="color:#999;font-size:12px">⚠️ 仅供参考，不构成投资建议 | 数据可能有延迟</p>"""


# ==================== 主流程 ====================

def main():
    print("⏳ 正在抓取数据，请稍候...")
    print()

    now_beijing = datetime.now(BEIJING_TZ)
    date_str = now_beijing.strftime("%Y年%m月%d日 %H:%M (北京时间)")
    briefing_type = "🌅 盘前简报" if is_morning() else "🌙 收盘简报"

    print(f"  📋 简报类型: {briefing_type}")
    print("  → A 股行情...")
    a_share = get_a_share_snapshot()

    print("  → A 股新闻...")
    a_news = get_a_share_news()

    print("  → 美股行情...")
    us_market = get_us_market_snapshot()

    print("  → 全球宏观新闻...")
    global_news = get_global_news()

    print("  → 原油价格...")
    oil = get_oil_price()

    print("  → 中国国航...")
    air_china = get_air_china_stock()

    print("  → 美伊/中东局势...")
    me_news = get_middle_east_news()

    print_report(date_str, a_share, a_news, us_market, global_news, oil, air_china, me_news)

    # 推送到手机
    push_content = build_push_content(a_share, a_news, us_market, global_news, oil, air_china, me_news)
    push_to_phone(f"📊 {briefing_type} - {now_beijing.strftime('%m月%d日 %H:%M')}", push_content)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("❌ 脚本运行失败:")
        traceback.print_exc()
        exit(1)
