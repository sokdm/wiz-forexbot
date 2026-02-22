from flask import Flask
from config.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    from app.extensions import db, login_manager
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprints
    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.admin import bp as admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Create upload folder
    import os
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    # Setup database within app context
    with app.app_context():
        # Import models here where app context is active
        from app.models import User, Analysis, AdView, Transaction
        
        # Create all tables
        db.create_all()
        
        # Create admin user
        from werkzeug.security import generate_password_hash
        try:
            admin_exists = User.query.filter_by(email=Config.ADMIN_EMAIL).first()
            if not admin_exists:
                admin = User(
                    username='admin',
                    email=Config.ADMIN_EMAIL,
                    password_hash=generate_password_hash('admin123'),
                    is_admin=True,
                    credits=999999
                )
                db.session.add(admin)
                db.session.commit()
                print("=" * 50)
                print("ADMIN CREATED")
                print(f"Email: {Config.ADMIN_EMAIL}")
                print("Password: admin123")
                print("=" * 50)
        except Exception as e:
            print(f"Note: {e}")
            db.session.rollback()

    return app

from app.extensions import login_manager

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))
