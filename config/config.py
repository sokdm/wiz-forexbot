import os

class Config:
    SECRET_KEY = 'wizforex-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///wizforex.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'app/static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    INITIAL_CREDITS = 1000
    ANALYSIS_COST = 50
    AD_REWARD = 200
    ADMIN_EMAIL = 'wsdmpresh@gmail.com'
