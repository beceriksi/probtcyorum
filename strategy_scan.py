import os, time, requests, pandas as pd, numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MEXC_FAPI = "https://contract.mexc.com"
BINANCE_API = "https://api-gcp.binance.com"

# ----------------------------
def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def telegram_send(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram yok:\n", text); return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    except:
        pass

def jget(url, params=None, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except: time.sleep(1)
    return None

# ----------------------------
def btc_trend():
    """BTC yön filtresi (Binance spot üzerinden)"""
    d = jget(f"{BINANCE_API}/api/v3/klines", {"symbol":"BTCUSDT", "interval":"4h", "limit":200})
    if not d: return "NÖTR"
    df = pd.DataFrame(d, columns=["t","o","h","l","c","v","ct","x1","x2","x3","x4","x5"])
    df = df.astype(float)
    ema20 = df["c"].ewm(span=20).mean().iloc[-1]
    ema50 = df["c"].ewm(span=50).mean().iloc[-1]
    rsi = calc_rsi(df["c"],14).iloc[-1]
    if ema20 > ema50 and rsi > 50: return "GÜÇLÜ"
    elif ema20 < ema50 and rsi < 50: return "ZAYIF"
    else: return "NÖTR"

# ----------------------------
def futures_symbols():
    d = jget(f"{MEXC_FAPI}/api/v1/contract/detail")
    if not d or "data" not in d: return []
    return [s["symbol"] for s in d["data"] if s.get("quoteCoin")=="USDT"]

def klines(symbol, interval="4h", limit=200):
    d = jget(f"{MEXC_FAPI}/api/v1/contract/kline/{symbol}", {"interval": interval, "limit": limit})
    if not d or "data" not in d: return None
    df = pd.DataFrame(d["data"], columns=["t","o","h","l","c","v","turn"])
    df = df.astype(float)
    return df

def calc_rsi(s, n=14):
    d=s.diff(); up=d.clip(lower=0); dn=-d.clip(upper=0)
    rs=up.ewm(alpha=1/n).mean()/(dn.ewm(alpha=1/n).mean()+1e-12)
    return 100-(100/(1+rs))

def ema(x,n): return x.ewm(span=n).mean()

def volume_spike(df, n=20, r=2.0):
    if len(df)<n+2: return False
    base = df["v"].iloc[-n:].mean()
    return df["v"].iloc[-1] > base*r

def bos_up(df, n=40): return df["c"].iloc[-1] > df["h"].iloc[-n:].max()
def bos_dn(df, n=40): return df["c"].iloc[-1] < df["l"].iloc[-n:].min()

# ----------------------------
def analyze(symbol, btc_state):
    df = klines(symbol,"4h",250)
    if df is None or len(df)<100: return None
    c=df["c"]
    ema20, ema50 = ema(c,20).iloc[-1], ema(c,50).iloc[-1]
    rsi = calc_rsi(c,14).iloc[-1]
    bosUp, bosDn = bos_up(df), bos_dn(df)
    vol = volume_spike(df,20,2.0)
    if not vol: return None
    trend = "↑" if ema20>ema50 else "↓"
    side=None
    if btc_state=="GÜÇLÜ" and trend=="↑" and bosUp and rsi>50:
        side="AL"
    elif btc_state=="ZAYIF" and trend=="↓" and bosDn and rsi<50:
        side="SAT"
    if side:
        return f"{symbol} — {side} | Trend:{trend} | RSI:{rsi:.1f} | Hacim↑ | BoS:{'↑' if bosUp else ('↓' if bosDn else '-')}"
    return None

# ----------------------------
def main():
    btc_state = btc_trend()
    syms = futures_symbols()
    if not syms:
        telegram_send("⚠️ Coin listesi alınamadı (MEXC).")
        return
    msg=[f"⏱ {ts()} — *Strateji Taraması (BTC: {btc_state})*"]
    signals=[]
    for i,s in enumerate(syms):
        try:
            res=analyze(s, btc_state)
            if res: signals.append(res)
        except: pass
        if i%15==0: time.sleep(0.3)
    if not signals:
        msg.append("ℹ️ Şu an kriterlere uyan sinyal yok.")
    else:
        msg.extend(signals[:20])
    telegram_send("\n".join(msg))

if __name__=="__main__":
    main()
