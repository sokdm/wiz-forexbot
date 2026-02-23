from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from bson.objectid import ObjectId
from app.extensions import mongo

class User(UserMixin):
    def __init__(self, user_data):
        self._id = str(user_data.get('_id')) if user_data.get('_id') else None
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.password_hash = user_data.get('password_hash')
        self.credits = user_data.get('credits', 1000)
        self.is_admin = user_data.get('is_admin', False)
    
    def get_id(self):
        return self._id
    
    @property
    def is_active(self):
        return True
    
    @staticmethod
    def find_by_email(email):
        user_data = mongo.db.users.find_one({'email': email.lower()})
        return User(user_data) if user_data else None
    
    @staticmethod
    def find_by_id(user_id):
        try:
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            return User(user_data) if user_data else None
        except:
            return None
    
    def save(self):
        user_data = {
            'username': self.username,
            'email': self.email.lower(),
            'password_hash': self.password_hash,
            'credits': self.credits,
            'is_admin': self.is_admin
        }
        if self._id:
            mongo.db.users.update_one({'_id': ObjectId(self._id)}, {'$set': user_data})
        else:
            result = mongo.db.users.insert_one(user_data)
            self._id = str(result.inserted_id)
        return self
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
