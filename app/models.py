from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re

db = SQLAlchemy()

def demicrosoft(fn):
    fn = re.sub("[^0-9a-zA-Z ]+", "", fn)
    for ch in [' ']:
        fn = fn.replace(ch,"_")
    return fn

class ShoreDivingReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shorediving_id = db.Column(db.String)
    shorediving_url = db.Column(db.String)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'))

    review = db.relationship("Review", back_populates="shorediving_data", uselist=False)

    def get_dict(self):
        return {
            'shorediving_url': self.shorediving_url,
            'id': self.id
        }

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    display_name = db.Column(db.String)
    username = db.Column(db.String, unique=True)
    profile_pic = db.Column(db.String)
    password = db.Column(db.String)
    registered_on = db.Column(db.DateTime, nullable=False,
        default=datetime.utcnow)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    is_fake=db.Column(db.Boolean, default=False)

    reviews = db.relationship(
        "Review",
        backref=db.backref('user', lazy=True),
        order_by="asc(Review.date_dived)",
    )
    images = db.relationship("Image")

    def get_dict(self):
        data = self.__dict__
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        data.pop('password', None)
        try:
            data.pop('email')
        except KeyError:
            pass
        try:
            data.pop('is_fake')
        except KeyError:
            pass
        try:
            data.pop('admin')
        except KeyError:
            pass
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
    max_depth = db.Column(db.String)
    last_review_date = db.Column(db.DateTime)
    last_review_viz = db.Column(db.Integer)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    submitter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    google_place_id = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    locality_id = db.Column(db.Integer, db.ForeignKey('locality.id'), nullable=True)
    area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'), nullable=True)
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")
    submitter = db.relationship("User", uselist=False)

    def get_basic_data(self):
        data = {}
        keys = [
            'name',
            'hero_img',
            'rating',
            'num_reviews',
            'location_city',
        ]
        for key in keys:
            data[key] = self.get(key)
        return data

    def get_dict(self):
        data = self.__dict__
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        data['url'] = '/Beach/'+str(self.id)+'/'+demicrosoft(self.name).lower()
        return data

    def get_url(self):
        return Spot.create_url(self.id, self.name)

    def get_beach_name_for_url(self):
        return demicrosoft(self.name).lower()

    @classmethod
    def create_url(cls, id, name):
        return '/Beach/'+str(id)+'/'+demicrosoft(name).lower()

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

    images = db.relationship("Image", backref=db.backref('review', lazy=True))
    shorediving_data = db.relationship("ShoreDivingReview", back_populates="review", uselist=False)

    def get_dict(self):
        data = self.__dict__
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        return data

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def get_dict(self):
        return {
            'url': self.url,
            'id': self.id
        }

#City
class Locality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'))
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))

    spots = db.relationship('Spot', backref='locality', lazy=True)

#County
class AreaTwo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))

    localities = db.relationship('Locality', backref='area_two', lazy=True)
    spots = db.relationship('Spot', backref='area_two', lazy=True)

#State
class AreaOne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))

    area_twos = db.relationship('AreaTwo', backref='area_one', lazy=True)
    localities = db.relationship('Locality', backref='area_one', lazy=True)
    spots = db.relationship('Spot', backref='area_one', lazy=True)

#Country
class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)

    area_ones = db.relationship('AreaOne', backref='country', lazy=True)
    area_twos = db.relationship('AreaTwo', backref='country', lazy=True)
    localities = db.relationship('Locality', backref='country', lazy=True)
    spots = db.relationship('Spot', backref='country', lazy=True)
