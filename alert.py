import os, json, time, requests
from datetime import datetime, timezone, timedelta

BASE = "https://api.india.delta.exchange"  # use https://api.delta.exchange if you use Delta global
SYMBOL = "BTCUSD"
IST = timezone(timedelta(hours=5, minutes=30))
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT = os.environ["TG_CHAT"]
HOURS = {15: (13 * 60, 21 * 60), 30: (11 * 60, 19 * 60)}  # IST, minutes of day
EXPIRY = 10


def send(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data={"chat_id": TG_CHAT, "text": text},
        timeout=20,
    ).raise_for_status()


def closed_candles(mins):
    now = int(time.time())
    r = requests.get(
        f"{BASE}/v2/history/candles",
        params={"resolution": f"{mins}m", "symbol": SYMBOL,
                "start": now - mins * 60 * 12, "end": now},
        timeout=20,
    )
    r.raise_for_status()
    data = sorted(r.json()["result"], key=lambda c: c["time"])
    return [c for c in data if c["time"] + mins * 60 <= now]


try:
    state = json.load(open("state.json"))
    first_run = False
except Exception:
    state = {}
    first_run = True

if first_run:
    send("MC alert bot connected. You will get a message when an MC + inside candle forms.")

for mins in (15, 30):
    cs = closed_candles(mins)
    if len(cs) < 2:
        continue
    last = state.get(str(mins))
    idx = [i for i in range(1, len(cs)) if last is None or cs[i]["time"] > last]
    if last is None:
        idx = idx[-1:]
    for i in idx:
        mc, ins = cs[i - 1], cs[i]
        close_t = ins["time"] + mins * 60
        if time.time() - close_t > 3600:
            continue
        dt = datetime.fromtimestamp(ins["time"], IST)
        mod = dt.hour * 60 + dt.minute
        start, end = HOURS[mins]
        inside = ins["high"] <= mc["high"] and ins["low"] >= mc["low"]
        if inside and dt.weekday() < 5 and start <= mod < end:
            till = datetime.fromtimestamp(close_t + EXPIRY * mins * 60, IST).strftime("%H:%M")
            send(
                f"MC SETUP {mins}m\n"
                f"Buy Stop (MC High): {mc['high']}\n"
                f"Sell Stop (MC Low): {mc['low']}\n"
                f"Valid till {till} IST (10 candles)"
            )
    state[str(mins)] = cs[-1]["time"]

json.dump(state, open("state.json", "w"))
