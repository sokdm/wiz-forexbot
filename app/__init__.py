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
   
   # CRITICAL: user_loader MUST be defined here after init_app
   @login_manager.user_loader
   def load_user(user_id):
       from app.models import User
       try:
           return User.query.get(int(user_id))
       except:
           return None
   
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
   
   # Initialize database (moved to function, runs once)
   init_database(app)
   
   return app

def init_database(app):
   """Initialize database and create admin user"""
   with app.app_context():
       from app.extensions import db
       from app.models import User
       from werkzeug.security import generate_password_hash
       
       # Create tables
       db.create_all()
       
       # Create admin if not exists
       try:
           from config.config import Config
           admin_email = getattr(Config, 'ADMIN_EMAIL', 'admin@wizforex.com')
           admin_exists = User.query.filter_by(email=admin_email).first()
           if not admin_exists:
               admin = User(
                   username='admin',
                   email=admin_email,
                   password_hash=generate_password_hash('admin123'),
                   is_admin=True,
                   credits=999999
               )
               db.session.add(admin)
               db.session.commit()
               print("=" * 50)
               print("ADMIN CREATED")
               print(f"Email: {admin_email}")
               print("Password: admin123")
               print("=" * 50)
       except Exception as e:
           print(f"Admin setup note: {e}")
           db.session.rollback()
