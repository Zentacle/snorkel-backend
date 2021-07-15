from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re

db = SQLAlchemy()

def demicrosoft(fn):
    fn = re.sub('[()]', '', fn)
    for ch in [' ']:
        fn = fn.replace(ch,"_")
    return fn

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

    def get_dict(self):
        data = self.__dict__
        data = self.__dict__
        data.pop('password', None)
        data.pop('_sa_instance_state', None)
        return data

class Spot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    hero_img = db.Column(db.String)
    location_google = db.Column(db.String)
    location_city = db.Column(db.String)
    description = db.Column(db.String)
    rating = db.Column(db.String)
    num_reviews = db.Column(db.Integer, default=0)
    entry_map = db.Column(db.String)
    # max_depth = db.Column(db.String)
    last_review_date = db.Column(db.DateTime)
    last_review_viz = db.Column(db.Integer)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")

    def get_dict(self):
        data = self.__dict__
        data.pop('_sa_instance_state', None)
        data['url'] = '/Beach/'+str(self.id)+'/'+demicrosoft(self.name)
        return data

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)
    visibility = db.Column(db.Integer, nullable=True) # in ft
    date_posted = db.Column(db.DateTime, nullable=False,
        default=datetime.utcnow)
    date_dived = db.Column(db.DateTime, nullable=True,
        default=datetime.utcnow)
    activity_type = db.Column(db.String)

    def get_dict(self):
        data = self.__dict__
        data.pop('_sa_instance_state', None)
        return data

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
