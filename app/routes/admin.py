from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func
from datetime import datetime, timedelta

from app.extensions import db
from app.models import User, Analysis, Transaction, AdView
from config.config import Config

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_analyses = Analysis.query.count()
    total_transactions = Transaction.query.count()
    total_ads = AdView.query.count()
    
    credits_spent = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.type == 'DEBIT'
    ).scalar() or 0
    
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    new_users_today = User.query.filter(User.created_at >= today_start).count()
    analyses_today = Analysis.query.filter(Analysis.created_at >= today_start).count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_analyses = Analysis.query.order_by(Analysis.created_at.desc()).limit(10).all()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    stats = {
        'total_users': total_users,
        'total_analyses': total_analyses,
        'total_transactions': total_transactions,
        'total_ads_watched': total_ads,
        'credits_spent': credits_spent,
        'new_users_today': new_users_today,
        'analyses_today': analyses_today,
        'recent_users': recent_users,
        'recent_analyses': recent_analyses,
        'recent_transactions': recent_transactions
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    
    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('admin/users.html', users=users, search=search)

@bp.route('/user/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    analyses = Analysis.query.filter_by(user_id=user_id).order_by(
        Analysis.created_at.desc()
    ).limit(50).all()
    
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(
        Transaction.created_at.desc()
    ).limit(50).all()
    
    return render_template('admin/user_detail.html', 
                         user=user, analyses=analyses, transactions=transactions)

@bp.route('/user/<int:user_id>/add-credits', methods=['POST'])
@login_required
@admin_required
def add_credits(user_id):
    user = User.query.get_or_404(user_id)
    amount = request.form.get('amount', type=int)
    
    if amount and amount > 0:
        user.credits += amount
        db.session.add(Transaction(
            user_id=user.id,
            type='ADMIN_CREDIT',
            amount=amount,
            description=f'Admin credit by {current_user.username}'
        ))
        db.session.commit()
        flash(f'Added {amount} credits to {user.username}', 'success')
    else:
        flash('Invalid amount', 'error')
    
    return redirect(url_for('admin.user_detail', user_id=user_id))

@bp.route('/user/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Cannot modify your own admin status', 'error')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        status = 'granted' if user.is_admin else 'revoked'
        flash(f'Admin {status} for {user.username}', 'success')
    
    return redirect(url_for('admin.user_detail', user_id=user_id))

@bp.route('/user/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Cannot ban yourself', 'error')
    else:
        user.is_active = False
        db.session.commit()
        flash(f'User {user.username} has been banned', 'success')
    
    return redirect(url_for('admin.users'))

@bp.route('/analyses')
@login_required
@admin_required
def analyses():
    page = request.args.get('page', 1, type=int)
    pair = request.args.get('pair', '')
    
    query = Analysis.query
    if pair:
        query = query.filter(Analysis.pair == pair.upper())
    
    analyses = query.order_by(Analysis.created_at.desc()).paginate(
        page=page, per_page=100, error_out=False
    )
    
    pairs = db.session.query(Analysis.pair).distinct().all()
    
    return render_template('admin/analyses.html', 
                         analyses=analyses, pairs=pairs, selected_pair=pair)

@bp.route('/transactions')
@login_required
@admin_required
def transactions():
    page = request.args.get('page', 1, type=int)
    transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=100, error_out=False)
    
    return render_template('admin/transactions.html', transactions=transactions)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        try:
            analysis_cost = request.form.get('analysis_cost', '50')
            ad_reward = request.form.get('ad_reward', '10')
            daily_credits = request.form.get('daily_credits', '0')
            
            Config.ANALYSIS_COST = int(analysis_cost) if analysis_cost.strip() else 50
            Config.AD_REWARD = int(ad_reward) if ad_reward.strip() else 10
            Config.DAILY_FREE_CREDITS = int(daily_credits) if daily_credits.strip() else 0
            
            flash('Settings updated successfully', 'success')
            return redirect(url_for('admin.settings'))
        except ValueError:
            flash('Invalid value entered. Please use numbers only.', 'error')
            return redirect(url_for('admin.settings'))
    
    return render_template('admin/settings.html', config=Config)

@bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    return jsonify({
        'users': User.query.count(),
        'analyses_today': Analysis.query.filter(
            Analysis.created_at >= datetime.utcnow().date()
        ).count(),
        'active_now': User.query.filter(
            User.last_login >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
    })
