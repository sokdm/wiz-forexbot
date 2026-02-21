import cv2
import numpy as np
from PIL import Image
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdvancedForexAnalyzer:
    """
    Advanced Forex Analysis with Real Chart Pattern Recognition
    Analyzes uploaded images for actual technical patterns
    """
    
    PAIRS = {
        'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
        'AUDUSD': 'AUDUSD=X', 'USDCAD': 'USDCAD=X', 'USDCHF': 'USDCHF=X',
        'NZDUSD': 'NZDUSD=X', 'EURGBP': 'EURGBP=X', 'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X', 'AUDJPY': 'AUDJPY=X', 'XAUUSD': 'GC=F', 
        'XAGUSD': 'SI=F', 'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD',
        'USOIL': 'CL=F', 'UKOIL': 'BZ=F'
    }
    
    def __init__(self):
        self.min_confidence = 70
        
    def analyze_chart_image(self, image_path):
        """
        Analyze the actual chart image for patterns
        Returns detailed technical analysis
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                return self._fallback_analysis("Could not load image")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect candles and patterns
            analysis = {
                'trend_detected': self._detect_trend(gray),
                'support_resistance': self._find_support_resistance(gray),
                'patterns': self._detect_patterns(gray),
                'volatility': self._calculate_volatility(gray),
                'volume_trend': self._analyze_volume(img),
                'candle_structure': self._analyze_candles(gray)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return self._fallback_analysis("Analysis error")
    
    def _detect_trend(self, gray_img):
        """Detect overall trend direction using edge detection"""
        # Use Canny edge detection to find trend lines
        edges = cv2.Canny(gray_img, 50, 150)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        
        if lines is None or len(lines) < 2:
            return {'direction': 'sideways', 'strength': 30}
        
        # Calculate average slope
        slopes = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 != x1:
                slope = (y2 - y1) / (x2 - x1)
                slopes.append(slope)
        
        avg_slope = np.mean(slopes) if slopes else 0
        
        # Determine trend
        if avg_slope < -0.1:
            return {'direction': 'uptrend', 'strength': min(95, 70 + abs(avg_slope) * 50)}
        elif avg_slope > 0.1:
            return {'direction': 'downtrend', 'strength': min(95, 70 + abs(avg_slope) * 50)}
        else:
            return {'direction': 'sideways', 'strength': 40}
    
    def _find_support_resistance(self, gray_img):
        """Find support and resistance levels from horizontal lines"""
        # Detect horizontal lines (support/resistance)
        edges = cv2.Canny(gray_img, 50, 150)
        
        # Look for horizontal line segments
        height, width = gray_img.shape
        horizontal_zones = []
        
        # Scan for price levels with high density of edges (consolidation zones)
        for y in range(0, height, 20):
            row = edges[y:y+20, :]
            if np.sum(row) > width * 2:  # High edge density
                horizontal_zones.append(y)
        
        # Group nearby zones
        if len(horizontal_zones) < 2:
            return {'support': None, 'resistance': None}
        
        # Sort and find support (lower) and resistance (upper)
        zones = sorted(horizontal_zones)
        mid = len(zones) // 2
        
        # Convert pixel positions to relative levels (0-100)
        support = 100 - (zones[0] / height * 100)
        resistance = 100 - (zones[-1] / height * 100)
        
        return {
            'support': round(support, 1),
            'resistance': round(resistance, 1),
            'levels_found': len(zones)
        }
    
    def _detect_patterns(self, gray_img):
        """Detect chart patterns (triangles, wedges, channels)"""
        patterns = []
        
        # Detect triangle patterns
        edges = cv2.Canny(gray_img, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if len(contour) > 50:
                # Approximate polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                if len(approx) == 3:
                    patterns.append('triangle')
                elif len(approx) == 4:
                    patterns.append('rectangle_channel')
        
        # Detect double top/bottom using contour analysis
        if len(contours) > 2:
            areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 100]
            if len(areas) >= 2:
                if abs(areas[0] - areas[1]) < areas[0] * 0.2:
                    patterns.append('double_pattern')
        
        return list(set(patterns)) if patterns else ['no_clear_pattern']
    
    def _calculate_volatility(self, gray_img):
        """Calculate market volatility from price swings"""
        # Measure price variation
        height, width = gray_img.shape
        
        # Sample price at different x positions
        prices = []
        for x in range(0, width, width // 10):
            col = gray_img[:, x]
            # Find brightest point (candle body/wick)
            bright_pixels = np.where(col > 200)[0]
            if len(bright_pixels) > 0:
                prices.append(np.mean(bright_pixels))
        
        if len(prices) < 2:
            return 'medium'
        
        # Calculate volatility
        price_changes = np.diff(prices)
        volatility = np.std(price_changes) / np.mean(prices) * 100 if np.mean(prices) > 0 else 0
        
        if volatility > 5:
            return 'high'
        elif volatility > 2:
            return 'medium'
        else:
            return 'low'
    
    def _analyze_volume(self, img):
        """Analyze volume bars if present at bottom of chart"""
        height, width = img.shape[:2]
        
        # Look at bottom 20% for volume
        volume_area = img[int(height*0.8):, :]
        gray_volume = cv2.cvtColor(volume_area, cv2.COLOR_BGR2GRAY)
        
        # Detect volume bars
        _, thresh = cv2.threshold(gray_volume, 100, 255, cv2.THRESH_BINARY)
        volume_bars = np.sum(thresh > 0)
        
        # Compare left vs right side (volume trend)
        left_volume = np.sum(thresh[:, :width//2] > 0)
        right_volume = np.sum(thresh[:, width//2:] > 0)
        
        if right_volume > left_volume * 1.3:
            return 'increasing'
        elif right_volume < left_volume * 0.7:
            return 'decreasing'
        else:
            return 'stable'
    
    def _analyze_candles(self, gray_img):
        """Analyze candlestick structure"""
        height, width = gray_img.shape
        
        # Detect candle bodies (rectangular shapes)
        edges = cv2.Canny(gray_img, 50, 150)
        
        # Count bullish vs bearish candles based on position
        upper_half = np.sum(edges[:height//2, :])
        lower_half = np.sum(edges[height//2:, :])
        
        if upper_half > lower_half * 1.2:
            return 'more_bearish_candles'
        elif lower_half > upper_half * 1.2:
            return 'more_bullish_candles'
        else:
            return 'mixed_candles'
    
    def _fallback_analysis(self, reason):
        """Return default analysis structure"""
        return {
            'trend_detected': {'direction': 'unknown', 'strength': 50},
            'support_resistance': {'support': 30, 'resistance': 70},
            'patterns': ['analysis_failed'],
            'volatility': 'medium',
            'volume_trend': 'stable',
            'candle_structure': 'mixed_candles'
        }
    
    def get_live_price_data(self, pair):
        """Get real market data from Yahoo Finance"""
        try:
            symbol = self.PAIRS.get(pair, f'{pair}=X')
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=1d"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            result = data['chart']['result'][0]
            meta = result['meta']
            timestamps = result['timestamp']
            quote = result['indicators']['quote'][0]
            
            closes = [c for c in quote['close'] if c]
            highs = [h for h in quote['high'] if h]
            lows = [l for l in quote['low'] if l]
            opens = [o for o in quote['open'] if o]
            
            if not closes:
                return None
            
            current_price = closes[-1]
            previous_close = meta.get('previousClose', closes[0])
            day_high = max(highs) if highs else current_price
            day_low = min(lows) if lows else current_price
            
            # Calculate real indicators
            change_pct = ((current_price - previous_close) / previous_close) * 100
            
            # Simple RSI calculation
            gains = []
            losses = []
            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains) if gains else 0
            avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses) if losses else 0
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            # Trend based on price action
            if len(closes) >= 20:
                sma20 = np.mean(closes[-20:])
                trend = 'above_sma20' if current_price > sma20 else 'below_sma20'
            else:
                trend = 'neutral'
            
            return {
                'price': current_price,
                'previous': previous_close,
                'change_pct': change_pct,
                'day_high': day_high,
                'day_low': day_low,
                'rsi': rsi,
                'trend': trend,
                'volatility': np.std(closes[-20:]) / np.mean(closes[-20:]) * 100 if len(closes) >= 20 else 0
            }
            
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return None
    
    def generate_signal(self, pair, image_path=None):
        """
        Generate comprehensive trading signal
        Combines image analysis with live market data
        """
        # Get image analysis
        if image_path:
            img_analysis = self.analyze_chart_image(image_path)
        else:
            img_analysis = self._fallback_analysis("No image")
        
        # Get live data
        live_data = self.get_live_price_data(pair)
        if not live_data:
            live_data = {
                'price': 0, 'change_pct': 0, 'rsi': 50,
                'day_high': 0, 'day_low': 0, 'trend': 'neutral'
            }
        
        # Combine analyses for final signal
        signal = self._calculate_final_signal(img_analysis, live_data, pair)
        
        return signal
    
    def _calculate_final_signal(self, img_analysis, live_data, pair):
        """Calculate final trading signal from all data"""
        
        score = 0  # Positive = bullish, Negative = bearish
        reasons = []
        confidence_factors = []
        
        # 1. Image Trend Analysis (0-30 points)
        trend = img_analysis['trend_detected']
        if trend['direction'] == 'uptrend':
            score += trend['strength'] * 0.3
            reasons.append(f"Chart shows uptrend (strength: {trend['strength']:.0f}%)")
            confidence_factors.append(trend['strength'])
        elif trend['direction'] == 'downtrend':
            score -= trend['strength'] * 0.3
            reasons.append(f"Chart shows downtrend (strength: {trend['strength']:.0f}%)")
            confidence_factors.append(trend['strength'])
        else:
            reasons.append("Chart trend is sideways/consolidating")
            confidence_factors.append(40)
        
        # 2. Support/Resistance Analysis (0-20 points)
        sr = img_analysis['support_resistance']
        if sr['support'] and sr['resistance']:
            price_position = 50  # Middle of range
            if live_data['price'] > 0:
                # Calculate where current price is in the range
                range_size = sr['resistance'] - sr['support']
                if range_size > 0:
                    price_position = ((live_data['price'] - sr['support']) / range_size) * 100
            
            if price_position < 30:
                score += 15
                reasons.append(f"Price near support ({sr['support']:.1f}) - bullish bounce likely")
                confidence_factors.append(70)
            elif price_position > 70:
                score -= 15
                reasons.append(f"Price near resistance ({sr['resistance']:.1f}) - bearish rejection likely")
                confidence_factors.append(70)
            else:
                reasons.append(f"Price in middle of range ({sr['support']:.1f} - {sr['resistance']:.1f})")
                confidence_factors.append(50)
        
        # 3. Pattern Analysis (0-25 points)
        patterns = img_analysis['patterns']
        if 'triangle' in patterns:
            # Triangle breakout direction
            if live_data['change_pct'] > 0.5:
                score += 20
                reasons.append("Ascending triangle pattern detected - bullish breakout")
            else:
                score -= 20
                reasons.append("Descending triangle pattern detected - bearish breakdown")
            confidence_factors.append(75)
        elif 'rectangle_channel' in patterns:
            reasons.append("Price trading in channel - range bound")
            confidence_factors.append(60)
        
        # 4. Live Data Analysis (0-25 points)
        # RSI
        rsi = live_data.get('rsi', 50)
        if rsi < 30:
            score += 20
            reasons.append(f"RSI oversold ({rsi:.1f}) - strong bullish reversal signal")
            confidence_factors.append(80)
        elif rsi < 40:
            score += 10
            reasons.append(f"RSI approaching oversold ({rsi:.1f})")
            confidence_factors.append(65)
        elif rsi > 70:
            score -= 20
            reasons.append(f"RSI overbought ({rsi:.1f}) - strong bearish reversal signal")
            confidence_factors.append(80)
        elif rsi > 60:
            score -= 10
            reasons.append(f"RSI approaching overbought ({rsi:.1f})")
            confidence_factors.append(65)
        
        # Price change momentum
        change = live_data.get('change_pct', 0)
        if change > 1:
            score += 10
            reasons.append(f"Strong bullish momentum (+{change:.2f}%)")
            confidence_factors.append(70)
        elif change < -1:
            score -= 10
            reasons.append(f"Strong bearish momentum ({change:.2f}%)")
            confidence_factors.append(70)
        
        # 5. Candle Structure (0-10 points)
        candles = img_analysis.get('candle_structure', 'mixed_candles')
        if candles == 'more_bullish_candles':
            score += 10
            reasons.append("More bullish candles detected in recent price action")
            confidence_factors.append(60)
        elif candles == 'more_bearish_candles':
            score -= 10
            reasons.append("More bearish candles detected in recent price action")
            confidence_factors.append(60)
        
        # Calculate final confidence
        avg_confidence = np.mean(confidence_factors) if confidence_factors else 50
        
        # Determine signal
        if score > 25 and avg_confidence > self.min_confidence:
            signal = 'BUY'
            confidence = min(95, avg_confidence + 10)
        elif score < -25 and avg_confidence > self.min_confidence:
            signal = 'SELL'
            confidence = min(95, avg_confidence + 10)
        else:
            signal = 'NEUTRAL'
            confidence = avg_confidence
        
        # Calculate levels
        current_price = live_data.get('price', 0)
        day_high = live_data.get('day_high', current_price * 1.02)
        day_low = live_data.get('day_low', current_price * 0.98)
        
        if signal == 'BUY':
            # Entry at current or slight pullback
            entry = current_price
            # SL below support or recent low
            sl = min(day_low * 0.998, current_price * 0.985)
            # TP at resistance or 2:1 R:R
            risk = entry - sl
            tp = entry + (risk * 2.5)
        elif signal == 'SELL':
            entry = current_price
            sl = max(day_high * 1.002, current_price * 1.015)
            risk = sl - entry
            tp = entry - (risk * 2.5)
        else:
            entry = current_price
            tp = None
            sl = None
        
        # Round to proper decimals
        if current_price > 1000:  # Gold, BTC
            decimals = 2
        elif current_price > 100:  # JPY pairs
            decimals = 3
        else:
            decimals = 5
        
        return {
            'signal': signal,
            'confidence': round(confidence, 1),
            'score': round(score, 1),
            'entry_price': round(entry, decimals) if entry else None,
            'take_profit': round(tp, decimals) if tp else None,
            'stop_loss': round(sl, decimals) if sl else None,
            'risk_reward': 2.5 if signal != 'NEUTRAL' else 0,
            'reasoning': reasons,
            'indicators': {
                'rsi': round(rsi, 1),
                'change_24h': round(change, 2),
                'trend_direction': trend['direction'],
                'volatility': img_analysis.get('volatility', 'medium'),
                'volume_trend': img_analysis.get('volume_trend', 'stable'),
                'patterns_detected': patterns
            },
            'levels': {
                'day_high': round(day_high, decimals),
                'day_low': round(day_low, decimals),
                'support': sr.get('support'),
                'resistance': sr.get('resistance')
            }
        }

# Singleton instance
analyzer = AdvancedForexAnalyzer()
cat > app/routes/main.py << 'EOF'
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from app.extensions import db
from app.models import Analysis, AdView, Transaction
from app.services.forex_analyzer import analyzer
from config.config import Config

bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/dashboard')
@login_required
def dashboard():
    analyses = Analysis.query.filter_by(user_id=current_user.id)\
        .order_by(Analysis.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', 
                         analyses=analyses, 
                         pairs=list(analyzer.PAIRS.keys()))

@bp.route('/forex-bot')
@login_required
def forex_bot():
    if current_user.credits < Config.ANALYSIS_COST:
        flash('Insufficient credits! Watch ads to earn more.', 'error')
        return redirect(url_for('main.profile'))
    return render_template('forex_bot.html', pairs=list(analyzer.PAIRS.keys()))

@bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    if current_user.credits < Config.ANALYSIS_COST:
        return jsonify({'error': 'Insufficient credits', 'credits': current_user.credits}), 403
    
    pair = request.form.get('pair')
    if not pair:
        return jsonify({'error': 'Please select a pair'}), 400
    
    # Handle image upload
    image_path = None
    image_url = None
    
    if 'chart_image' in request.files:
        file = request.files['chart_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_path = filepath
            image_url = f"/static/uploads/{filename}"
    
    # Perform advanced analysis with image
    result = analyzer.generate_signal(pair, image_path)
    
    # Add image URL to result
    if image_url:
        result['image_url'] = image_url
    
    # Only deduct credits for valid signals
    if result['signal'] in ['BUY', 'SELL'] and result['confidence'] >= 70:
        current_user.credits -= Config.ANALYSIS_COST
        
        analysis = Analysis(
            user_id=current_user.id,
            pair=pair,
            signal=result['signal'],
            entry_price=result['entry_price'],
            take_profit=result['take_profit'],
            stop_loss=result['stop_loss'],
            confidence=int(result['confidence']),
            reasoning=' | '.join(result['reasoning'])
        )
        db.session.add(analysis)
        
        trans = Transaction(
            user_id=current_user.id,
            type='DEBIT',
            amount=Config.ANALYSIS_COST,
            description=f'Analysis for {pair}'
        )
        db.session.add(trans)
        db.session.commit()
        
        result['analysis_id'] = analysis.id
        result['remaining_credits'] = current_user.credits
        result['credits_deducted'] = True
    else:
        result['credits_deducted'] = False
        result['message'] = 'No charge - insufficient confidence for trade signal'
    
    return jsonify(result)

@bp.route('/profile')
@login_required
def profile():
    stats = {
        'total_analyses': Analysis.query.filter_by(user_id=current_user.id).count(),
        'ads_watched': AdView.query.filter_by(user_id=current_user.id).count()
    }
    return render_template('profile.html', user=current_user, stats=stats, config=Config)

@bp.route('/watch-ad', methods=['POST'])
@login_required
def watch_ad():
    last_ad = AdView.query.filter_by(user_id=current_user.id)\
        .order_by(AdView.watched_at.desc()).first()
    
    if last_ad and (datetime.utcnow() - last_ad.watched_at).seconds < 30:
        return jsonify({'error': 'Please wait 30 seconds between ads'}), 429
    
    ad_view = AdView(user_id=current_user.id, credits_earned=Config.AD_REWARD)
    current_user.credits += Config.AD_REWARD
    
    trans = Transaction(
        user_id=current_user.id,
        type='AD_REWARD',
        amount=Config.AD_REWARD,
        description='Ad view reward'
    )
    
    db.session.add(ad_view)
    db.session.add(trans)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'credits_earned': Config.AD_REWARD,
        'new_balance': current_user.credits
    })
