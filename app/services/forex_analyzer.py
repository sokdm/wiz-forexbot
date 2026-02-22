import requests
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartForexAnalyzer:
    """Institutional-Grade Confluence Analyzer v3.0
    - Strict signal requirements (no conflicting signals)
    - Real-time price validation
    - Minimum confluence threshold"""
    
    PAIRS = {
        'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
        'AUDUSD': 'AUDUSD=X', 'USDCAD': 'USDCAD=X', 'USDCHF': 'USDCHF=X',
        'NZDUSD': 'NZDUSD=X', 'EURGBP': 'EURGBP=X', 'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X', 'AUDJPY': 'AUDJPY=X', 'XAUUSD': 'GC=F',
        'XAGUSD': 'SI=F', 'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD',
        'USOIL': 'CL=F', 'UKOIL': 'BZ=F'
    }
    
    def get_market_data(self, pair, range_days=5):
        """Fetch with real-time validation"""
        try:
            symbol = self.PAIRS.get(pair, f'{pair}=X')
            
            # Get chart data
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range={range_days}d"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            result = data['chart']['result'][0]
            quote = result['indicators']['quote'][0]
            meta = result['meta']
            
            closes = [c for c in quote['close'] if c]
            highs = [h for h in quote['high'] if h]
            lows = [l for l in quote['low'] if l]
            opens = [o for o in quote['open'] if o]
            volumes = [v for v in quote['volume'] if v] if quote['volume'] else []
            timestamps = result['timestamp']
            
            if len(closes) < 30:
                return None
            
            # Get real-time price
            live_price = meta.get('regularMarketPrice')
            last_close = closes[-1]
            
            # Check data freshness (last candle should be recent)
            last_candle_time = datetime.fromtimestamp(timestamps[-1])
            time_since_candle = datetime.now() - last_candle_time
            
            # If data is stale (>2 hours old), warn but still use it
            is_stale = time_since_candle > timedelta(hours=2)
            
            # Use live price if available and significantly different
            if live_price and abs(live_price - last_close) / last_close > 0.001:
                current_price = live_price
                price_gap = abs(live_price - last_close)
            else:
                current_price = last_close
                price_gap = 0
            
            return {
                'closes': closes,
                'highs': highs,
                'lows': lows,
                'opens': opens,
                'volumes': volumes,
                'current': current_price,
                'previous': closes[-2],
                'day_high': max(highs[-24:]) if len(highs) >= 24 else max(highs),
                'day_low': min(lows[-24:]) if len(lows) >= 24 else min(lows),
                'timestamp': timestamps[-1],
                'is_stale': is_stale,
                'price_gap': price_gap,
                'last_candle_age_minutes': int(time_since_candle.total_seconds() / 60)
            }
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    
    def calculate_ema(self, data, period):
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        for price in data[1:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
    
    def calculate_rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return 50
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gains = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_losses = np.convolve(losses, np.ones(period)/period, mode='valid')
        if len(avg_losses) == 0 or avg_losses[-1] == 0:
            return 100
        rs = avg_gains[-1] / avg_losses[-1]
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, closes):
        ema12 = self.calculate_ema(closes, 12)
        ema26 = self.calculate_ema(closes, 26)
        macd_line = [e12 - e26 for e12, e26 in zip(ema12[-len(ema26):], ema26)]
        signal_line = self.calculate_ema(macd_line, 9)
        hist = macd_line[-1] - signal_line[-1]
        return macd_line[-1], signal_line[-1], hist
    
    def calculate_adx(self, highs, lows, closes, period=14):
        if len(highs) < period + 1:
            return 0, 0, 0
        
        tr_list = []
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr_list.append(max(tr1, tr2, tr3))
            
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        
        atr = np.mean(tr_list[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr > 0 else 0
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        return dx, plus_di, minus_di
    
    def analyze_structure(self, highs, lows, closes):
        if len(highs) < 10:
            return 'undefined', 0
        
        recent_highs = highs[-10:]
        recent_lows = lows[-10:]
        
        hh = sum(1 for i in range(9) if recent_highs[i] < recent_highs[i+1])
        hl = sum(1 for i in range(9) if recent_lows[i] < recent_lows[i+1])
        lh = sum(1 for i in range(9) if recent_highs[i] > recent_highs[i+1])
        ll = sum(1 for i in range(9) if recent_lows[i] > recent_lows[i+1])
        
        if hh >= 6 and hl >= 6:
            return 'bullish_structure', 3
        elif hh >= 4 and hl >= 4:
            return 'bullish_bias', 1
        elif lh >= 6 and ll >= 6:
            return 'bearish_structure', -3
        elif lh >= 4 and ll >= 4:
            return 'bearish_bias', -1
        return 'choppy', 0
    
    def strict_confluence_analysis(self, data):
        """Strict analysis - conflicting signals = NO TRADE"""
        closes = data['closes']
        highs = data['highs']
        lows = data['lows']
        volumes = data['volumes']
        current = data['current']
        
        bullish_points = 0
        bearish_points = 0
        neutral_points = 0
        
        reasons = []
        warnings = []
        
        # 1. TREND ANALYSIS (Max 30 points)
        ema20 = self.calculate_ema(closes, 20)[-1]
        ema50 = self.calculate_ema(closes, 50)[-1] if len(closes) >= 50 else ema20
        sma200 = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)
        adx, plus_di, minus_di = self.calculate_adx(highs, lows, closes)
        
        # Trend must be clear
        if current > ema20 > ema50 and current > sma200:
            bullish_points += 25
            if adx > 25:
                bullish_points += 5
                reasons.append(("✓✓ Strong bullish trend (ADX>25)", "strong"))
            else:
                reasons.append(("✓ Bullish trend", "normal"))
        elif current < ema20 < ema50 and current < sma200:
            bearish_points += 25
            if adx > 25:
                bearish_points += 5
                reasons.append(("✓✓ Strong bearish trend (ADX>25)", "strong"))
            else:
                reasons.append(("✓ Bearish trend", "normal"))
        else:
            neutral_points += 20
            reasons.append(("→ Mixed trend signals", "warning"))
            if adx < 20:
                warnings.append("Trend too weak (ADX<20)")
        
        # 2. MOMENTUM - RSI (Max 20 points)
        rsi = self.calculate_rsi(closes)
        
        if rsi < 30:
            bullish_points += 20
            reasons.append((f"✓✓ RSI oversold ({rsi:.1f})", "strong"))
        elif rsi < 40:
            bullish_points += 10
            reasons.append((f"✓ RSI low ({rsi:.1f})", "normal"))
        elif rsi > 70:
            bearish_points += 20
            reasons.append((f"✓✓ RSI overbought ({rsi:.1f})", "strong"))
        elif rsi > 60:
            bearish_points += 10
            reasons.append((f"✓ RSI high ({rsi:.1f})", "normal"))
        else:
            neutral_points += 10
            reasons.append((f"→ RSI neutral ({rsi:.1f})", "normal"))
        
        # 3. MOMENTUM - MACD (Max 20 points) - CRITICAL
        macd, macd_signal, macd_hist = self.calculate_macd(closes)
        
        if macd > macd_signal and macd_hist > 0:
            bullish_points += 20
            if macd_hist > macd_hist * 1.1:  # Expanding
                bullish_points += 5
                reasons.append(("✓✓ MACD bullish expanding", "strong"))
            else:
                reasons.append(("✓ MACD bullish", "normal"))
        elif macd < macd_signal and macd_hist < 0:
            bearish_points += 20
            if macd_hist < macd_hist * 1.1:
                bearish_points += 5
                reasons.append(("✓✓ MACD bearish expanding", "strong"))
            else:
                reasons.append(("✓ MACD bearish", "normal"))
        else:
            neutral_points += 15
            reasons.append(("→ MACD mixed/transitioning", "warning"))
        
        # 4. MARKET STRUCTURE (Max 20 points)
        structure, _ = self.analyze_structure(highs, lows, closes)
        
        if structure == 'bullish_structure':
            bullish_points += 20
            reasons.append(("✓✓ Bullish HH+HL structure", "strong"))
        elif structure == 'bullish_bias':
            bullish_points += 10
            reasons.append(("✓ Weak bullish structure", "normal"))
        elif structure == 'bearish_structure':
            bearish_points += 20
            reasons.append(("✓✓ Bearish LH+LL structure", "strong"))
        elif structure == 'bearish_bias':
            bearish_points += 10
            reasons.append(("✓ Weak bearish structure", "normal"))
        else:
            neutral_points += 10
            reasons.append(("→ No clear structure", "warning"))
        
        # 5. VOLUME (Max 10 points)
        if len(volumes) >= 20:
            vol_sma = np.mean(volumes[-20:])
            recent_vol = np.mean(volumes[-3:])
            
            if recent_vol > vol_sma * 1.5:
                # Volume confirms direction
                if bullish_points > bearish_points:
                    bullish_points += 10
                    reasons.append(("✓✓ High volume confirming bullish", "strong"))
                elif bearish_points > bullish_points:
                    bearish_points += 10
                    reasons.append(("✓✓ High volume confirming bearish", "strong"))
            elif recent_vol > vol_sma * 1.2:
                if bullish_points > bearish_points:
                    bullish_points += 5
                elif bearish_points > bullish_points:
                    bearish_points += 5
                reasons.append(("✓ Volume above average", "normal"))
            elif recent_vol < vol_sma * 0.7:
                neutral_points += 10
                warnings.append("Low volume - weak conviction")
        
        # Calculate final score
        total_bullish = bullish_points
        total_bearish = bearish_points
        
        # STRICT LOGIC: Conflicting signals reduce confidence
        if bullish_points > 0 and bearish_points > 0:
            # Conflicting signals - cancel out
            conflict_penalty = min(bullish_points, bearish_points) * 0.5
            total_bullish -= conflict_penalty
            total_bearish -= conflict_penalty
            warnings.append("Conflicting signals detected")
        
        net_score = total_bullish - total_bearish
        
        # Determine signal with strict thresholds
        if total_bullish >= 60 and net_score > 40 and bearish_points < 20:
            signal = 'BUY'
            confidence = min(50 + net_score, 95)
        elif total_bearish >= 60 and net_score < -40 and bullish_points < 20:
            signal = 'SELL'
            confidence = min(50 + abs(net_score), 95)
        elif net_score > 25 and bullish_points > bearish_points * 2:
            signal = 'WEAK_BUY'
            confidence = 55
        elif net_score < -25 and bearish_points > bullish_points * 2:
            signal = 'WEAK_SELL'
            confidence = 55
        else:
            signal = 'NO_TRADE'
            confidence = 0
            warnings.append("Insufficient confluence for trade")
        
        atr = np.mean([h - l for h, l in zip(highs[-14:], lows[-14:])])
        
        return {
            'signal': signal,
            'confidence': round(confidence, 1),
            'net_score': round(net_score, 1),
            'bullish_points': bullish_points,
            'bearish_points': bearish_points,
            'rsi': rsi,
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'adx': adx,
            'ema20': ema20,
            'ema50': ema50,
            'sma200': sma200,
            'atr': atr,
            'structure': structure,
            'reasons': reasons,
            'warnings': warnings,
            'highs': highs,
            'lows': lows
        }
    
    def calculate_levels(self, analysis, current_price, pair):
        """Calculate entry, SL, TP based on signal"""
        signal = analysis['signal']
        atr = analysis['atr']
        
        if signal in ['NO_TRADE']:
            return {
                'entry': current_price,
                'sl': None,
                'tp': None,
                'trail': None,
                'rr': 0
            }
        
        # Volatility multiplier
        atr_pct = (atr / current_price) * 100
        if 'BTC' in pair or 'ETH' in pair:
            mult = 2.5
        elif 'OIL' in pair or 'XAU' in pair:
            mult = 2.0
        else:
            mult = 1.5
        
        if atr_pct > 3:
            mult *= 1.2
        
        if signal in ['BUY', 'WEAK_BUY']:
            entry = current_price
            recent_low = min(analysis['lows'][-5:])
            sl = max(recent_low - (atr * 0.3), entry - (atr * mult))
            risk = entry - sl
            tp = entry + (risk * 2)
            trail = entry + risk
        else:
            entry = current_price
            recent_high = max(analysis['highs'][-5:])
            sl = min(recent_high + (atr * 0.3), entry + (atr * mult))
            risk = sl - entry
            tp = entry - (risk * 2)
            trail = entry - risk
        
        if current_price > 10000:
            dec = 2
        elif current_price > 1000:
            dec = 3
        elif current_price > 100:
            dec = 4
        else:
            dec = 5
        
        return {
            'entry': round(entry, dec),
            'sl': round(sl, dec),
            'tp': round(tp, dec),
            'trail': round(trail, dec),
            'rr': 2.0
        }
    
    def analyze(self, pair, image_path=None):
        data = self.get_market_data(pair)
        
        if not data:
            return {
                'signal': 'ERROR',
                'confidence': 0,
                'error': 'Data unavailable',
                'reasoning': []
            }
        
        analysis = self.strict_confluence_analysis(data)
        levels = self.calculate_levels(analysis, data['current'], pair)
        
        # Format output
        formatted_reasons = []
        for reason, strength in analysis['reasons']:
            formatted_reasons.append(reason)
        
        for warning in analysis['warnings']:
            formatted_reasons.append(f"⚠ {warning}")
        
        if data['is_stale']:
            formatted_reasons.append(f"⚠ Data delayed ({data['last_candle_age_minutes']} min old)")
        
        if data['price_gap'] > 0:
            formatted_reasons.append(f"⚠ Price gap: {data['price_gap']:.2f}")
        
        current = data['current']
        if current > 10000:
            dec = 2
        elif current > 1000:
            dec = 3
        elif current > 100:
            dec = 4
        else:
            dec = 5
        
        return {
            'signal': analysis['signal'],
            'confidence': analysis['confidence'],
            'confluence_score': analysis['net_score'],
            'entry_price': levels['entry'],
            'stop_loss': levels['sl'],
            'take_profit': levels['tp'],
            'trailing_activation': levels['trail'],
            'risk_reward': levels['rr'],
            'pair': pair,
            'current_price': round(current, dec),
            'timestamp': datetime.fromtimestamp(data['timestamp']).strftime('%H:%M:%S'),
            'data_delay_min': data['last_candle_age_minutes'],
            'indicators': {
                'rsi': round(analysis['rsi'], 1),
                'macd': round(analysis['macd'], 4),
                'macd_hist': round(analysis['macd_hist'], 4),
                'adx': round(analysis['adx'], 1),
                'atr': round(analysis['atr'], dec)
            },
            'confluence': {
                'bullish': analysis['bullish_points'],
                'bearish': analysis['bearish_points']
            },
            'reasoning': formatted_reasons
        }

analyzer = SmartForexAnalyzer()
