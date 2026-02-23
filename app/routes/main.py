from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from app.extensions import db
from app.models import Analysis
from app.services.forex_analyzer import analyzer

bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/')
def index():
    return render_template('welcome.html')

@bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', pairs=list(analyzer.PAIRS.keys()))

@bp.route('/analyze', methods=['POST'])
def analyze():
    pair = request.form.get('pair')
    if not pair:
        return jsonify({'error': 'Please select a pair'}), 400

    # Handle image upload
    image_filename = None
    if 'chart_image' in request.files:
        file = request.files['chart_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"chart_{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_filename = filename

    # Perform analysis
    result = analyzer.analyze(pair)
    
    # Save analysis
    analysis = Analysis(
        user_id='anonymous',
        pair=pair,
        signal=result['signal'],
        entry_price=result.get('entry_price'),
        take_profit=result.get('take_profit'),
        stop_loss=result.get('stop_loss'),
        confidence=int(result['confidence']),
        reasoning=' | '.join(result['reasoning']),
        image_url=image_filename
    )
    db.session.add(analysis)
    db.session.commit()
    
    # Redirect to results page
    return redirect(url_for('main.results', analysis_id=analysis.id))

@bp.route('/results/<int:analysis_id>')
def results(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    # Parse reasoning back to list
    reasoning_list = analysis.reasoning.split(' | ') if analysis.reasoning else []
    
    return render_template('results.html', 
                         analysis=analysis,
                         reasoning_list=reasoning_list,
                         image_url=f"/static/uploads/{analysis.image_url}" if analysis.image_url else None)
