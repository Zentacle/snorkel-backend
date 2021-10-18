from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from app.helpers.demicrosoft import demicrosoft

db = SQLAlchemy()

class ShoreDivingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    name_url = db.Column(db.String)
    destination = db.Column(db.String)
    destination_url = db.Column(db.String)
    region = db.Column(db.String)
    region_url = db.Column(db.String)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)

    spot = db.relationship("Spot", back_populates="shorediving_data", uselist=False)

    def get_dict(self):
        return {
            'name': self.name,
            'id': self.id,
            'url': self.get_url(),
        }

    def get_url(self):
        return '/Earth/' + self.region_url + '/' + self.destination_url + '/' + self.name_url

    def get_region_dict(self):
        return {
            'short_name': self.region,
            'name': self.region_url,
            'url': self.get_region_url(),
        }

    def get_region_url(self):
        return '/Earth/' + self.region_url + '/index.htm'

    def get_destination_dict(self):
        return {
            'short_name': self.destination,
            'name': self.destination_url,
            'url': self.get_destination_url(),
        }

    def get_destination_url(self):
        return '/Earth/' + self.region_url + '/' + self.destination_url + '/index.htm'

    @classmethod
    def create_url(cls, shorediving_data):
        return '/Earth/' + shorediving_data.region_url + '/' + shorediving_data.destination_url + '/' + shorediving_data.name_url

class ShoreDivingReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shorediving_id = db.Column(db.String, unique=True)
    shorediving_url = db.Column(db.String)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'))
    entry = db.Column(db.Integer)
    bottom = db.Column(db.Integer)
    reef = db.Column(db.Integer)
    animal = db.Column(db.Integer)
    plant = db.Column(db.Integer)
    facilities = db.Column(db.Integer)
    crowds = db.Column(db.Integer)
    roads = db.Column(db.Integer)
    snorkel = db.Column(db.Integer)
    beginner = db.Column(db.Integer)
    intermediate = db.Column(db.Integer)
    advanced = db.Column(db.Integer)
    night = db.Column(db.Integer)
    visibility = db.Column(db.Integer)
    current = db.Column(db.Integer)
    surf = db.Column(db.Integer)
    average = db.Column(db.Float)

    review = db.relationship("Review", back_populates="shorediving_data", uselist=False)

    def get_dict(self):
        return {
            'shorediving_url': self.shorediving_url,
            'id': self.id,
            'shorediving_id': self.shorediving_id,
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
    hometown = db.Column(db.String)
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
        if self.username:
            data['username'] = self.username.lower()
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
    difficulty = db.Column(db.String)
    locality_id = db.Column(db.Integer, db.ForeignKey('locality.id'), nullable=True)
    area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'), nullable=True)
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True)
    noaa_station_id = db.Column(db.String)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")
    submitter = db.relationship("User", uselist=False)
    shorediving_data = db.relationship("ShoreDivingData", back_populates="spot", uselist=False)

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
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if data.get('shorediving_data'):
            data.pop('shorediving_data', None)
        data['url'] = '/Beach/'+str(self.id)+'/'+demicrosoft(self.name).lower()
        return data

    def get_url(self):
        return Spot.create_url(self.id, self.name)

    def get_beach_name_for_url(self):
        return demicrosoft(self.name).lower()

    @classmethod
    def create_url(cls, id, name):
        return '/Beach/'+str(id)+'/'+demicrosoft(name).lower()

    def get_confidence_score(self):
        import math
        z = 1.645 # 90% confidence interval (could 1.960 for 95%)
        std_dev = 0.50 # roughly calculated based on existing review data
        if self.num_reviews:
            return float(self.rating) - z * (std_dev/math.sqrt(self.num_reviews))
        else:
            return 0

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
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        return data

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    caption = db.Column(db.String)

    def get_dict(self):
        return {
            'url': self.url,
            'id': self.id,
            'review_id': self.review_id,
            'caption': self.caption,
        }

#City
class Locality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'))
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)

    spots = db.relationship('Spot', backref='locality', lazy=True)

    def get_dict(self, country=None, area_one=None, area_two=None):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if not self.short_name:
            data['short_name'] = self.get_short_name()
        if country and area_one and area_two:
            data['url'] = self.get_url(country, area_one, area_two)
        elif self.country and self.area_one and self.area_two:
            data['url'] = self.get_url(self.country, self.area_one, self.area_two)
        return data

    def get_short_name(self):
        return self.short_name.lower() if self.short_name else demicrosoft(self.name).lower()

    def get_url(self, country, area_one, area_two):
        return '/loc/' + country.short_name + '/' + area_one.short_name + '/' + area_two.short_name + '/' + self.get_short_name()

#County - Doesn't always exist
class AreaTwo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)

    localities = db.relationship('Locality', backref='area_two', lazy=True)
    spots = db.relationship('Spot', backref='area_two', lazy=True)

    def get_simple_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'short_name': self.short_name,
        }

    def get_dict(self, country=None, area_one=None):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if data.get('area_one_id'):
            data.pop('area_one_id', None)
        if data.get('country_id'):
            data.pop('country_id', None)
        if country and area_one:
            data['url'] = self.get_url(country, area_one)
        elif self.country and self.area_one:
            data['url'] = self.get_url(self.country, self.area_one)
        return data

    def get_url(self, country, area_one):
        return '/loc/' + country.short_name + '/' + area_one.short_name + '/' + self.short_name

#State
class AreaOne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)

    area_twos = db.relationship('AreaTwo', backref='area_one', lazy=True)
    localities = db.relationship('Locality', backref='area_one', lazy=True)
    spots = db.relationship('Spot', backref='area_one', lazy=True)

    def get_simple_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'short_name': self.short_name,
        }

    def get_dict(self, country=None):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if data.get('country_id'):
            data.pop('country_id', None)
        if country:
            data['url'] = self.get_url(country)
        elif self.country:
            data['url'] = self.get_url(self.country)
        return data

    def get_url(self, country):
        return '/loc/' + country.short_name + '/' + self.short_name

#Country
class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)

    area_ones = db.relationship('AreaOne', backref='country', lazy=True)
    area_twos = db.relationship('AreaTwo', backref='country', lazy=True)
    localities = db.relationship('Locality', backref='country', lazy=True)
    spots = db.relationship('Spot', backref='country', lazy=True)

    def get_simple_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'short_name': self.short_name,
        }

    def get_dict(self):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        data['url'] = self.get_url()
        return data

    def get_url(self):
        return '/loc/' + self.short_name
