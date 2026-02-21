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
    image_url = None
    
    if 'chart_image' in request.files:
        file = request.files['chart_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_url = f"/static/uploads/{filename}"
    
    # Perform analysis
    result = analyzer.analyze(pair)
    
    if image_url:
        result['image_url'] = image_url
    
    # Only charge for valid signals
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
