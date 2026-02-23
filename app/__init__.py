from flask import Flask
from config.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    from app.extensions import db
    db.init_app(app)
    
    from app.routes.main import bp as main_bp
    
    app.register_blueprint(main_bp)
    
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    with app.app_context():
        db.create_all()
    
    return app
