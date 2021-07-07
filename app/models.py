from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask import current_app as app
import jwt

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    display_name = db.Column(db.String)
    username = db.Column(db.String, unique=True)
    profile_pic = db.Column(db.String)
    password = db.Column(db.String)
    registered_on = db.Column(db.DateTime, nullable=False,
        default=datetime.utcnow)
    admin = db.Column(db.Boolean, nullable=False, default=False)

    reviews = db.relationship("Review", backref=db.backref('user', lazy=True))
    images = db.relationship("Image")

    # https://realpython.com/token-based-authentication-with-flask/
    def encode_auth_token(self, user_id):
        """
            Generates the Auth Token
            :return: string
        """
        try:
            payload = {
                'exp': datetime.utcnow() + timedelta(days=365),
                'iat': datetime.utcnow(),
                'sub': user_id
            }
            return jwt.encode(
                payload,
                app.config.get('SECRET_KEY'),
                algorithm='HS256'
            )
        except Exception as e:
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        """
        Decodes the auth token
        :param auth_token:
        :return: integer|string
        """
        try:
            payload = jwt.decode(auth_token, app.config.get('SECRET_KEY'), algorithms="HS256")
            return payload['sub']
        except jwt.ExpiredSignatureError:
            return 'Signature expired. Please log in again.'
        except jwt.InvalidTokenError:
            return 'Invalid token. Please log in again.'

class Spot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    hero_img = db.Column(db.String)
    location_google = db.Column(db.String)
    location_city = db.Column(db.String)
    description = db.Column(db.String)
    rating = db.Column(db.Integer)
    num_reviews = db.Column(db.Integer)
    entry_map = db.Column(db.String)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)
    visibility = db.Column(db.Integer, nullable=True) # in ft
    date_posted = db.Column(db.DateTime, nullable=False,
        default=datetime.utcnow)
    activity_type = db.Column(db.String)

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)