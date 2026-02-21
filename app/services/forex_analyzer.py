import requests
import numpy as np
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartForexAnalyzer:
    """Smart analyzer using real market data and price action"""
    
    PAIRS = {
        'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
        'AUDUSD': 'AUDUSD=X', 'USDCAD': 'USDCAD=X', 'USDCHF': 'USDCHF=X',
        'NZDUSD': 'NZDUSD=X', 'EURGBP': 'EURGBP=X', 'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X', 'AUDJPY': 'AUDJPY=X', 'XAUUSD': 'GC=F',
        'XAGUSD': 'SI=F', 'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD',
        'USOIL': 'CL=F', 'UKOIL': 'BZ=F'
    }
    
    def get_market_data(self, pair):
        """Fetch real market data from Yahoo Finance"""
        try:
            symbol = self.PAIRS.get(pair, f'{pair}=X')
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=5d"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            result = data['chart']['result'][0]
            quote = result['indicators']['quote'][0]
            
            closes = [c for c in quote['close'] if c]
            highs = [h for h in quote['high'] if h]
            lows = [l for l in quote['low'] if l]
            opens = [o for o in quote['open'] if o]
            volumes = result['indicators']['quote'][0].get('volume', [])
            
            if not closes or len(closes) < 10:
                return None
            
            return {
                'closes': closes,
                'highs': highs,
                'lows': lows,
                'opens': opens,
                'volumes': [v for v in volumes if v] if volumes else [],
                'current': closes[-1],
                'previous': closes[-2] if len(closes) > 1 else closes[0],
                'day_high': max(highs[-24:]) if len(highs) >= 24 else max(highs),
                'day_low': min(lows[-24:]) if len(lows) >= 24 else min(lows)
            }
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def calculate_indicators(self, data):
        """Calculate technical indicators"""
        closes = data['closes']
        
        # RSI
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains)
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses)
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Moving averages
        sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
        
        # Trend detection
        if closes[-1] > sma20 > sma50:
            trend = 'strong_uptrend'
        elif closes[-1] > sma20:
            trend = 'uptrend'
        elif closes[-1] < sma20 < sma50:
            trend = 'strong_downtrend'
        elif closes[-1] < sma20:
            trend = 'downtrend'
        else:
            trend = 'sideways'
        
        # Volatility (ATR simplified)
        ranges = [h - l for h, l in zip(data['highs'][-14:], data['lows'][-14:])]
        atr = np.mean(ranges) if ranges else 0
        
        # Volume trend
        volumes = data.get('volumes', [])
        if len(volumes) >= 10:
            vol_trend = 'increasing' if volumes[-1] > np.mean(volumes[-10:-1]) else 'decreasing'
        else:
            vol_trend = 'neutral'
        
        return {
            'rsi': rsi,
            'sma20': sma20,
            'sma50': sma50,
            'trend': trend,
            'atr': atr,
            'vol_trend': vol_trend,
            'change_pct': ((closes[-1] - closes[0]) / closes[0]) * 100
        }
    
    def detect_patterns(self, data):
        """Detect price action patterns"""
        highs = data['highs'][-20:]
        lows = data['lows'][-20:]
        closes = data['closes'][-20:]
        
        patterns = []
        
        # Higher highs / Lower lows
        if len(highs) >= 5:
            recent_highs = highs[-5:]
            recent_lows = lows[-5:]
            
            if all(recent_highs[i] < recent_highs[i+1] for i in range(len(recent_highs)-1)):
                patterns.append('higher_highs_bullish')
            elif all(recent_highs[i] > recent_highs[i+1] for i in range(len(recent_highs)-1)):
                patterns.append('lower_highs_bearish')
            
            if all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1)):
                patterns.append('higher_lows_bullish')
            elif all(recent_lows[i] > recent_lows[i+1] for i in range(len(recent_lows)-1)):
                patterns.append('lower_lows_bearish')
        
        # Support/Resistance test
        current = closes[-1]
        day_range = data['day_high'] - data['day_low']
        
        if day_range > 0:
            position = (current - data['day_low']) / day_range
            
            if position < 0.2:
                patterns.append('near_support')
            elif position > 0.8:
                patterns.append('near_resistance')
            elif 0.4 < position < 0.6:
                patterns.append('middle_of_range')
        
        # Candlestick patterns (simplified)
        if len(closes) >= 3:
            last_three = closes[-3:]
            if last_three[0] < last_three[1] < last_three[2]:
                patterns.append('three_white_soldiers')
            elif last_three[0] > last_three[1] > last_three[2]:
                patterns.append('three_black_crows')
        
        return patterns
    
    def analyze(self, pair, image_path=None):
        """Main analysis function"""
        data = self.get_market_data(pair)
        
        if not data:
            return {
                'signal': 'NEUTRAL',
                'confidence': 0,
                'error': 'Could not fetch market data',
                'reasoning': ['Market data unavailable']
            }
        
        indicators = self.calculate_indicators(data)
        patterns = self.detect_patterns(data)
        
        # Calculate signal score
        score = 0
        reasons = []
        
        # Trend analysis
        if indicators['trend'] == 'strong_uptrend':
            score += 30
            reasons.append('Strong uptrend: Price above SMA20 and SMA50')
        elif indicators['trend'] == 'uptrend':
            score += 20
            reasons.append('Uptrend: Price above SMA20')
        elif indicators['trend'] == 'strong_downtrend':
            score -= 30
            reasons.append('Strong downtrend: Price below SMA20 and SMA50')
        elif indicators['trend'] == 'downtrend':
            score -= 20
            reasons.append('Downtrend: Price below SMA20')
        
        # RSI analysis
        rsi = indicators['rsi']
        if rsi < 30:
            score += 25
            reasons.append(f'RSI oversold ({rsi:.1f}) - bullish reversal likely')
        elif rsi < 40:
            score += 15
            reasons.append(f'RSI approaching oversold ({rsi:.1f})')
        elif rsi > 70:
            score -= 25
            reasons.append(f'RSI overbought ({rsi:.1f}) - bearish reversal likely')
        elif rsi > 60:
            score -= 15
            reasons.append(f'RSI approaching overbought ({rsi:.1f})')
        
        # Pattern analysis
        for pattern in patterns:
            if 'bullish' in pattern:
                score += 15
                reasons.append(f'Bullish pattern: {pattern.replace("_", " ").title()}')
            elif 'bearish' in pattern:
                score -= 15
                reasons.append(f'Bearish pattern: {pattern.replace("_", " ").title()}')
            elif pattern == 'near_support':
                score += 10
                reasons.append('Price near daily support level')
            elif pattern == 'near_resistance':
                score -= 10
                reasons.append('Price near daily resistance level')
        
        # Volume confirmation
        if indicators['vol_trend'] == 'increasing':
            score = score * 1.2 if score > 0 else score * 0.8
            reasons.append('Volume increasing - confirming momentum')
        
        # Determine signal
        confidence = min(abs(score) + 50, 95)
        
        if score > 25:
            signal = 'BUY'
        elif score < -25:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
            confidence = 50
            reasons.append('Mixed signals - no clear directional bias')
        
        # Calculate levels
        current = data['current']
        atr = indicators['atr']
        
        if signal == 'BUY':
            entry = current
            sl = max(data['day_low'] * 0.998, current - (atr * 2))
            tp = current + ((current - sl) * 2.5)
        elif signal == 'SELL':
            entry = current
            sl = min(data['day_high'] * 1.002, current + (atr * 2))
            tp = current - ((sl - current) * 2.5)
        else:
            entry = current
            sl = None
            tp = None
        
        # Round decimals
        if current > 1000:
            decimals = 2
        elif current > 100:
            decimals = 3
        else:
            decimals = 5
        
        return {
            'signal': signal,
            'confidence': round(confidence, 1),
            'score': round(score, 1),
            'entry_price': round(entry, decimals),
            'take_profit': round(tp, decimals) if tp else None,
            'stop_loss': round(sl, decimals) if sl else None,
            'risk_reward': 2.5 if signal != 'NEUTRAL' else 0,
            'reasoning': reasons,
            'indicators': {
                'rsi': round(rsi, 1),
                'trend': indicators['trend'],
                'change_pct': round(indicators['change_pct'], 2),
                'patterns': patterns
            },
            'levels': {
                'day_high': round(data['day_high'], decimals),
                'day_low': round(data['day_low'], decimals)
            }
        }

analyzer = SmartForexAnalyzer()
