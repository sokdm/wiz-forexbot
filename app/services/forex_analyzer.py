import requests
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Signal(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    WEAK_SELL = "WEAK_SELL"
    NO_TRADE = "NO_TRADE"

@dataclass
class TFData:
    tf: str
    signal: Signal
    conf: float
    rsi: float
    adx: float
    trend: str
    price: float
    age: int
    max_age: int
    weight: float

class ProAnalyzer:
    PAIRS = {
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
        "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "XAUUSD": "GC=F",
        "XAGUSD": "SI=F", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
        "USOIL": "CL=F", "UKOIL": "BZ=F"
    }
    TFS = {
        "15m": {"i": "15m", "r": "10d", "w": 2.0, "max_age": 20},
        "1h": {"i": "1h", "r": "30d", "w": 1.5, "max_age": 90},
        "4h": {"i": "4h", "r": "90d", "w": 1.0, "max_age": 300}
    }
    
    def __init__(self):
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def get_live_price(self, pair):
        try:
            if "BTC" in pair or "ETH" in pair:
                cg_map = {"BTCUSD": "bitcoin", "ETHUSD": "ethereum"}
                if pair in cg_map:
                    r = requests.get(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={cg_map[pair]}&vs_currencies=usd",
                        timeout=5
                    )
                    if r.status_code == 200:
                        return r.json()[cg_map[pair]]["usd"]
        except:
            pass
        return None
    
    def fetch(self, pair, tf):
        try:
            sym = self.PAIRS.get(pair, f"{pair}=X")
            cfg = self.TFS[tf]
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={cfg['i']}&range={cfg['r']}"
            r = self.sess.get(url, timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            if not data.get("chart", {}).get("result"):
                return None
            
            res = data["chart"]["result"][0]
            qt = res["indicators"]["quote"][0]
            meta = res["meta"]
            ts = res["timestamp"]
            
            yahoo_live = meta.get("regularMarketPrice") or meta.get("postMarketPrice")
            alt_live = self.get_live_price(pair)
            
            clean = []
            for i in range(len(ts)):
                if all(qt[k][i] is not None for k in ["close", "high", "low", "open"]):
                    clean.append({
                        "t": ts[i],
                        "o": qt["open"][i],
                        "h": qt["high"][i],
                        "l": qt["low"][i],
                        "c": qt["close"][i],
                        "v": qt["volume"][i] or 0
                    })
            
            if len(clean) < 20:
                return None
            
            c = [d["c"] for d in clean]
            h = [d["h"] for d in clean]
            l = [d["l"] for d in clean]
            v = [d["v"] for d in clean]
            
            last_c = c[-1]
            curr = alt_live if alt_live else (yahoo_live if yahoo_live else last_c)
            
            last_t = datetime.fromtimestamp(clean[-1]["t"])
            age = int((datetime.now() - last_t).total_seconds() / 60)
            
            if age > cfg["max_age"] * 3:
                return None
            
            is_live = curr != last_c or age < 5
            return {
                "c": c, "h": h, "l": l, "v": v,
                "price": curr, "last_c": last_c,
                "age": age, "max_age": cfg["max_age"],
                "is_live": is_live
            }
        except Exception as e:
            logger.error(f"Error {pair} {tf}: {e}")
            return None
    
    def ema(self, d, p):
        if len(d) < p:
            return [d[-1]] * len(d)
        m = 2 / (p + 1)
        e = [sum(d[:p]) / p]
        for x in d[p:]:
            e.append((x - e[-1]) * m + e[-1])
        return [e[0]] * (p - 1) + e
    
    def rsi(self, c, p=14):
        if len(c) < p + 1:
            return 50
        d = np.diff(c)
        g = np.where(d > 0, d, 0)
        l = np.where(d < 0, -d, 0)
        ag = np.mean(g[:p])
        al = np.mean(l[:p])
        for i in range(p, len(g)):
            ag = (ag * (p - 1) + g[i]) / p
            al = (al * (p - 1) + l[i]) / p
        if al > 0:
            return 100 - (100 / (1 + ag / al))
        return 100
    
    def macd(self, c):
        e12 = self.ema(c, 12)
        e26 = self.ema(c, 26)
        ml = [a - b for a, b in zip(e12[-len(e26):], e26)]
        sl = self.ema(ml, 9)
        h = ml[-1] - sl[-1]
        ph = ml[-2] - sl[-2] if len(ml) > 1 else h
        
        if h > 0 and h > ph:
            st = "bullish_expanding"
        elif h > 0:
            st = "bullish_contracting"
        elif h < 0 and h < ph:
            st = "bearish_expanding"
        else:
            st = "bearish_contracting"
        return h, st
    
    def adx(self, h, l, c, p=14):
        if len(h) < p + 1:
            return 0
        tr = []
        pdm = []
        mdm = []
        for i in range(1, len(h)):
            tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
            um = h[i] - h[i - 1]
            dm = l[i - 1] - l[i]
            pdm.append(um if um > dm and um > 0 else 0)
            mdm.append(dm if dm > um and dm > 0 else 0)
        atr = sum(tr[-p:]) / p
        pdi = 100 * sum(pdm[-p:]) / p / atr if atr > 0 else 0
        mdi = 100 * sum(mdm[-p:]) / p / atr if atr > 0 else 0
        if (pdi + mdi) > 0:
            return 100 * abs(pdi - mdi) / (pdi + mdi)
        return 0
    
    def atr(self, h, l, c, p=14):
        if len(h) < p + 1:
            return 0
        tr_list = []
        for i in range(1, len(h)):
            tr_list.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
        return sum(tr_list[-p:]) / p
    
    def structure(self, h, l):
        if len(h) < 20:
            return "undefined", 0
        sh = [(i, h[i]) for i in range(2, len(h) - 2) 
              if h[i] > max(h[i - 2:i]) and h[i] > max(h[i + 1:i + 3])]
        sl = [(i, l[i]) for i in range(2, len(l) - 2) 
              if l[i] < min(l[i - 2:i]) and l[i] < min(l[i + 1:i + 3])]
        if len(sh) < 2 or len(sl) < 2:
            return "undefined", 0
        hh = 1 if sh[-1][1] > sh[-2][1] else -1
        hl = 1 if sl[-1][1] > sl[-2][1] else -1
        if hh == 1 and hl == 1:
            return "bullish_structure", 3
        elif hh == 1 or hl == 1:
            return "bullish_bias", 1.5
        elif hh == -1 and hl == -1:
            return "bearish_structure", -3
        elif hh == -1 or hl == -1:
            return "bearish_bias", -1.5
        return "choppy", 0
    
    def analyze_tf(self, d, tf):
        c, h, l, v = d["c"], d["h"], d["l"], d["v"]
        price = d["price"]
        
        ema9 = self.ema(c, 9)[-1]
        ema21 = self.ema(c, 21)[-1]
        ema50 = self.ema(c, 50)[-1] if len(c) >= 50 else self.ema(c, 21)[-1]
        
        rsi = self.rsi(c)
        macd_hist, macd_st = self.macd(c)
        adx = self.adx(h, l, c)
        struct, sstr = self.structure(h, l)
        atr = self.atr(h, l, c)
        
        # Determine trend
        if price > ema9 > ema21 > ema50:
            trend, esc = "strong_uptrend", 3
        elif price > ema9 > ema21:
            trend, esc = "uptrend", 2
        elif price > ema9:
            trend, esc = "weak_uptrend", 1
        elif price < ema9 < ema21 < ema50:
            trend, esc = "strong_downtrend", -3
        elif price < ema9 < ema21:
            trend, esc = "downtrend", -2
        elif price < ema9:
            trend, esc = "weak_downtrend", -1
        else:
            trend, esc = "ranging", 0
        
        score = 0
        reasons = []
        
        # RSI logic
        if rsi < 30:
            score += 3
            reasons.append(f"RSI oversold {rsi:.1f}")
        elif rsi < 40:
            score += 1
            reasons.append(f"RSI low {rsi:.1f}")
        elif rsi > 70:
            score -= 3
            reasons.append(f"RSI overbought {rsi:.1f}")
        elif rsi > 60:
            score -= 1
            reasons.append(f"RSI high {rsi:.1f}")
        else:
            reasons.append(f"RSI neutral {rsi:.1f}")
        
        # MACD logic
        if macd_hist > 0:
            if "expanding" in macd_st:
                score += 2
                reasons.append("MACD bullish expanding")
            else:
                score += 1
                reasons.append("MACD bullish")
        else:
            if "expanding" in macd_st:
                score -= 2
                reasons.append("MACD bearish expanding")
            else:
                score -= 1
                reasons.append("MACD bearish")
        
        # Trend and structure
        score += esc
        reasons.append(f"Trend: {trend}")
        score += sstr
        reasons.append(f"Structure: {struct}")
        reasons.append(f"ADX: {adx:.1f}")
        
        # Volatility check
        recent_vol = np.mean(v[-5:]) if len(v) >= 5 else np.mean(v)
        avg_vol = np.mean(v[-20:]) if len(v) >= 20 else np.mean(v)
        if avg_vol > 0 and recent_vol / avg_vol > 2:
            reasons.append("⚠ High volatility")
            score *= 0.85
        
        # Signal determination
        if score >= 4 and adx > 20:
            sig, conf = Signal.STRONG_BUY, min(85 + score, 98)
        elif score >= 2:
            sig, conf = Signal.BUY, min(75 + score, 90)
        elif score > 0:
            sig, conf = Signal.WEAK_BUY, 60 + score * 5
        elif score <= -4 and adx > 20:
            sig, conf = Signal.STRONG_SELL, min(85 + abs(score), 98)
        elif score <= -2:
            sig, conf = Signal.SELL, min(75 + abs(score), 90)
        elif score < 0:
            sig, conf = Signal.WEAK_SELL, 60 + abs(score) * 5
        else:
            sig, conf = Signal.NO_TRADE, 50
        
        if not d["is_live"]:
            conf *= 0.9
        if d["age"] > d["max_age"]:
            conf *= 0.8
        
        return TFData(tf, sig, conf, rsi, adx, trend, price, d["age"], d["max_age"], self.TFS[tf]["w"]), reasons, atr
    
    def aggregate(self, tf_results):
        if not tf_results:
            return Signal.NO_TRADE, 0, {}, ["No data"]
        
        # PRIORITY: 15m (chart timeframe) decides direction
        # Higher timeframes only confirm or add strength
        
        tf_15m = next((t for t, r, a in tf_results if t.tf == "15m"), None)
        tf_1h = next((t for t, r, a in tf_results if t.tf == "1h"), None)
        tf_4h = next((t for t, r, a in tf_results if t.tf == "4h"), None)
        
        all_reas = []
        for td, reas, _ in tf_results:
            all_reas.extend([f"[{td.tf}] {r}" for r in reas])
        
        prices = [td.price for td, _, _ in tf_results]
        avg_price = sum(prices) / len(prices)
        
        # If no 15m data, use what we have
        if not tf_15m:
            if tf_1h:
                return tf_1h.signal, tf_1h.conf, {"price": avg_price}, all_reas
            elif tf_4h:
                return tf_4h.signal, tf_4h.conf, {"price": avg_price}, all_reas
            else:
                return Signal.NO_TRADE, 0, {"price": avg_price}, all_reas
        
        # 15m is PRIMARY - it decides the signal
        primary_signal = tf_15m.signal
        primary_conf = tf_15m.conf
        
        # Check if higher timeframes agree
        htf_agreement = 0
        htf_count = 0
        
        for tf in [tf_1h, tf_4h]:
            if tf:
                htf_count += 1
                # Check agreement
                if "BUY" in primary_signal.value and "BUY" in tf.signal.value:
                    htf_agreement += 1
                elif "SELL" in primary_signal.value and "SELL" in tf.signal.value:
                    htf_agreement += 1
                elif primary_signal == Signal.NO_TRADE and tf.signal == Signal.NO_TRADE:
                    htf_agreement += 1
        
        # Adjust confidence based on HTF agreement
        if htf_count > 0:
            agreement_ratio = htf_agreement / htf_count
            if agreement_ratio >= 0.5:
                # HTF agrees - boost confidence
                primary_conf = min(primary_conf * 1.1, 98)
            else:
                # HTF disagrees - reduce confidence and weaken signal
                primary_conf = primary_conf * 0.7
                # Downgrade signal strength
                if primary_signal == Signal.STRONG_BUY:
                    primary_signal = Signal.BUY
                elif primary_signal == Signal.BUY:
                    primary_signal = Signal.WEAK_BUY
                elif primary_signal == Signal.STRONG_SELL:
                    primary_signal = Signal.SELL
                elif primary_signal == Signal.SELL:
                    primary_signal = Signal.WEAK_SELL
                all_reas.append("⚠ Higher timeframe disagreement - signal weakened")
        
        return primary_signal, primary_conf, {"price": avg_price}, all_reas
    
    def analyze(self, pair):
        tf_results = []
        for tf in ["15m", "1h", "4h"]:
            d = self.fetch(pair, tf)
            if d:
                td, reas, atr = self.analyze_tf(d, tf)
                tf_results.append((td, reas, atr))
        
        if not tf_results:
            return {
                "signal": "NO_TRADE",
                "confidence": 0,
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "reasoning": ["No data available"],
                "timeframes": {}
            }
        
        fs, conf, meta, reas = self.aggregate(tf_results)
        latest = tf_results[0]
        price = meta["price"]
        atr = latest[2]
        
        # Calculate levels based on signal direction
        signal_str = fs.value
        
        if "BUY" in signal_str and "SELL" not in signal_str:
            entry = price
            tp = price + (atr * 2) if atr else price * 1.02
            sl = price - (atr * 1) if atr else price * 0.99
        elif "SELL" in signal_str:
            entry = price
            tp = price - (atr * 2) if atr else price * 0.98
            sl = price + (atr * 1) if atr else price * 1.01
        else:
            entry = price
            tp = None
            sl = None
        
        return {
            "signal": fs.value,
            "confidence": round(conf, 1),
            "entry_price": round(entry, 5) if entry else None,
            "take_profit": round(tp, 5) if tp else None,
            "stop_loss": round(sl, 5) if sl else None,
            "reasoning": reas[:8],
            "timeframes": {t.tf: {"signal": t.signal.value, "conf": t.conf, "trend": t.trend} 
                          for t, r, a in tf_results}
        }

analyzer = ProAnalyzer()
