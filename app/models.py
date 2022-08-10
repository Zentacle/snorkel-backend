from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_method
from datetime import datetime, timedelta
from app.helpers.demicrosoft import demicrosoft
from flask import current_app
from sqlalchemy import func

db = SQLAlchemy()

tags = db.Table('tags',
                db.Column('tag_id', db.Integer, db.ForeignKey(
                    'tag.id'), primary_key=True),
                db.Column('spot_id', db.Integer, db.ForeignKey(
                    'spot.id'), primary_key=True)
                )


class ShoreDivingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    name_url = db.Column(db.String)
    destination = db.Column(db.String)
    destination_url = db.Column(db.String)
    region = db.Column(db.String)
    region_url = db.Column(db.String)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)

    spot = db.relationship(
        "Spot", back_populates="shorediving_data", uselist=False)

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

    review = db.relationship(
        "Review", back_populates="shorediving_data", uselist=False)

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
    is_fake = db.Column(db.Boolean, default=False)
    unit = db.Column(db.String, nullable=False, default='imperial')
    bio = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    reviews = db.relationship(
        "Review",
        backref=db.backref('user', lazy=True),
        order_by="asc(Review.date_dived)",
    )
    images = db.relationship("Image")

    def get_dict(self):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        data.pop('password', None)
        if self.username:
            data['username'] = self.username.lower()
        try:
            data.pop('email', None)
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
        data['has_pro'] = False
        return data

    @hybrid_method
    def distance(self, latitude, longitude):
        import math
        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude)
                   * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @distance.expression
    def distance(self, latitude, longitude):
        return func.sqrt(
            (
                func.pow(69.1 * (self.latitude - latitude), 2)
                + (func.pow(69.1 * (self.longitude - longitude)
                   * func.cos(self.latitude / 57.3), 2))
            )
        )


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
    is_deleted = db.Column(db.Boolean, default=False)
    submitter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    google_place_id = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    difficulty = db.Column(db.String)
    locality_id = db.Column(
        db.Integer, db.ForeignKey('locality.id'), nullable=True)
    area_two_id = db.Column(
        db.Integer, db.ForeignKey('area_two.id'), nullable=True)
    area_one_id = db.Column(
        db.Integer, db.ForeignKey('area_one.id'), nullable=True)
    country_id = db.Column(
        db.Integer, db.ForeignKey('country.id'), nullable=True)
    noaa_station_id = db.Column(db.String)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")
    submitter = db.relationship("User", uselist=False)
    shorediving_data = db.relationship(
        "ShoreDivingData", back_populates="spot", uselist=False)
    wannadive_data = db.relationship(
        "WannaDiveData", back_populates="spot", uselist=False)
    tags = db.relationship('Tag', secondary=tags, lazy='subquery',
                           backref=db.backref('spot', lazy=True))

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
        if data.get('is_verified'):
            data.pop('is_verified', None)
        if data.get('is_deleted'):
            data.pop('is_deleted', None)
        if not data.get('description').strip():
            data['description'] = f"{data.get('name')} is a {data.get('rating') if data.get('rating') else 0}-star" \
                f" rated scuba dive and snorkel destination in {data.get('location_city')} which is accessible from" \
                f" shore based on {data.get('num_reviews')} ratings."
        if not data.get('difficulty'):
            data['difficulty'] = 'Unrated'
        if data.get('tags'):
            data['access'] = []
            for tag in data.get('tags'):
                data['access'].append(tag.get_dict())
            data.pop('tags', None)
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
        z = 1.645  # 90% confidence interval (could 1.960 for 95%)
        std_dev = 0.50  # roughly calculated based on existing review data
        if self.num_reviews:
            return float(self.rating) - z * (std_dev/math.sqrt(self.num_reviews))
        else:
            return 0

    @hybrid_method
    def distance(self, latitude, longitude):
        import math
        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude)
                   * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @distance.expression
    def distance(self, latitude, longitude):
        return func.sqrt(
            (
                func.pow(69.1 * (self.latitude - latitude), 2)
                + (func.pow(69.1 * (self.longitude - longitude)
                   * func.cos(self.latitude / 57.3), 2))
            )
        )

    @hybrid_method
    def sqlite3_distance(self, latitude, longitude):
        import math
        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude)
                   * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @sqlite3_distance.expression
    def sqlite3_distance(self, latitude, longitude):
        return func.abs(
            (69.1 * (self.latitude - latitude) * 69.1 * (self.latitude - latitude))
            + (
                (69.1 * (self.longitude - longitude))
                * (69.1 * (self.longitude - longitude))
            )
        )


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)
    visibility = db.Column(db.Integer, nullable=True)  # in ft
    date_posted = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    date_dived = db.Column(db.DateTime, nullable=True,
                           default=datetime.utcnow)
    activity_type = db.Column(db.String)
    title = db.Column(db.String)
    dive_length = db.Column(db.Integer)
    entry = db.Column(db.String)
    weight = db.Column(db.Integer)
    start_air = db.Column(db.Integer)
    end_air = db.Column(db.Integer)
    air_type = db.Column(db.String)
    air_temp = db.Column(db.Integer)
    water_temp = db.Column(db.Integer)
    max_depth = db.Column(db.Integer)
    difficulty = db.Column(db.String)
    dive_shop_id = db.Column(db.Integer, db.ForeignKey('dive_shop.id'))

    dive_shop = db.relationship("DiveShop", uselist=False)
    images = db.relationship("Image", backref=db.backref('review', lazy=True))
    shorediving_data = db.relationship(
        "ShoreDivingReview", back_populates="review", uselist=False)

    def get_simple_dict(self):
        keys = [
            'id',
            'rating',
            'text',
            'date_dived',
            'date_posted',
            'activity_type',
            'title',
        ]
        data = {}
        for key in keys:
            data[key] = self.get(key)
        return data

    def get_dict(self):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if not data.get('title') and self.spot.name:
            data['title'] = self.spot.name
        if data.get('spot'):
            data.pop('spot', None)
        return data


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(
        db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    caption = db.Column(db.String)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def get_dict(self):
        return {
            'url': f'https://www.zentacle.com/image/reviews/{self.url}',
            'id': self.id,
            'review_id': self.review_id,
            'caption': self.caption,
        }

# City


class Locality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'))
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    spots = db.relationship('Spot', backref='locality', lazy=True)
    shops = db.relationship('DiveShop', backref='locality', lazy=True)

    def get_dict(self, country=None, area_one=None, area_two=None):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        if not self.short_name:
            data['short_name'] = self.get_short_name()
        if country and area_one:
            data['url'] = self.get_url(country, area_one, area_two)
        elif self.country and self.area_one:
            data['url'] = self.get_url(
                self.country, self.area_one, self.area_two)
        return data

    def get_short_name(self):
        return self.short_name.lower() if self.short_name else demicrosoft(self.name).lower()

    def get_url(self, country, area_one, area_two):
        return '/loc/' + country.short_name + '/' + area_one.short_name + '/' + (area_two.short_name if area_two else '_') + '/' + self.get_short_name()

# County - Doesn't always exist


class AreaTwo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    localities = db.relationship('Locality', backref='area_two', lazy=True)
    spots = db.relationship('Spot', backref='area_two', lazy=True)
    shops = db.relationship('DiveShop', backref='area_two', lazy=True)

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

# State


class AreaOne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True, nullable=False)
    map_image_url = db.Column(db.String)

    area_twos = db.relationship('AreaTwo', backref='area_one', lazy=True)
    localities = db.relationship('Locality', backref='area_one', lazy=True)
    spots = db.relationship('Spot', backref='area_one', lazy=True)
    shops = db.relationship('DiveShop', backref='area_one', lazy=True)

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

# Country


class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    area_ones = db.relationship('AreaOne', backref='country', lazy=True)
    area_twos = db.relationship('AreaTwo', backref='country', lazy=True)
    localities = db.relationship('Locality', backref='country', lazy=True)
    spots = db.relationship('Spot', backref='country', lazy=True)
    shops = db.relationship('DiveShop', backref='country', lazy=True)

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


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, unique=True, nullable=False)

    def get_dict(self):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        return data


class WannaDiveData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)

    spot = db.relationship(
        "Spot", back_populates="wannadive_data", uselist=False)


class DiveShop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    padi_store_id = db.Column(db.String, unique=True)
    name = db.Column(db.String)
    description = db.Column(db.String)
    hours = db.Column(db.JSON(none_as_null=True))
    website = db.Column(db.String)
    fareharbor_url = db.Column(db.String)
    address1 = db.Column(db.String)
    address2 = db.Column(db.String)
    city = db.Column(db.String)
    state = db.Column(db.String)
    zip = db.Column(db.String)
    country_name = db.Column(db.String)
    logo_img = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    locality_id = db.Column(
        db.Integer, db.ForeignKey('locality.id'), nullable=True)
    area_two_id = db.Column(
        db.Integer, db.ForeignKey('area_two.id'), nullable=True)
    area_one_id = db.Column(
        db.Integer, db.ForeignKey('area_one.id'), nullable=True)
    country_id = db.Column(
        db.Integer, db.ForeignKey('country.id'), nullable=True)
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True)
    stamp_uri = db.Column(db.String, nullable=True)
    owner = db.relationship("User", uselist=False)

    def get_simple_dict(self):
        simpleDict = {
            'id': self.id,
            'name': self.name,
            'website': self.website,
            'logo_img': self.logo_img,
            "fareharbor_url": self.fareharbor_url,
            "city": self.city,
            "state": self.state,
            "country_name": self.country_name,
            'address1': self.address1,
            'address2': self.address2,
            'zip': self.zip,
        }
        simpleDict["url"] = DiveShop.get_shop_url(self)
        return simpleDict

    def get_dict(self):
        dict = {
            'id': self.id,
            'name': self.name,
            'website': self.website,
            "fareharbor_url": self.fareharbor_url,
            'logo_img': self.logo_img,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address1': self.address1,
            'address2': self.address2,
            "city": self.city,
            "state": self.state,
            "owner_user_id": self.owner_user_id,
            "stamp_uri": self.stamp_uri,
            "phone": self.phone,
            "description": self.description,
            "hours": self.hours,
            "country_name": self.country_name,
            'zip': self.zip,
        }

        dict["full_address"] = DiveShop.get_full_address(
            self.address1,
            self.address2,
            self.city,
            self.state,
            self.zip,
            self.country_name
        )
        dict["url"] = DiveShop.get_shop_url(self)
        if not self.description:
            name = self.name
            city = str(self.city or '') + ', ' + str(self.country_name or '')
            dict['description'] = f'{name} is a scuba dive shop based in {city}. They are a PADI certified dive shop' \
                'and offer a variety of dive and snorkel related services, gear, and guided tours.'
        return dict

    @classmethod
    def get_shop_url(cls, shop):
        url_name = demicrosoft(shop.name).lower()
        id = shop.id
        return f'/shop/{id}/{url_name}'

    @classmethod
    def get_full_address(cls, address1, address2, city, state, zip, country):
        full_address = ''
        if address1:
            full_address += address1
        if address2:
            full_address += ' ' + address2
        if city:
            if full_address == "":
                full_addres += city
            else:
                full_address += ', ' + city
        if state:
            if full_address == "":
                full_address += state
            else:
                full_address += ', ' + state
        if zip:
            full_address += ' ' + zip
        if country:
            if full_address == "":
                full_address += country
            else:
                full_address += ', ' + country
        return full_address

    @hybrid_method
    def distance(self, latitude, longitude):
        import math
        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude)
                   * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @distance.expression
    def distance(self, latitude, longitude):
        return func.sqrt(
            (
                func.pow(69.1 * (self.latitude - latitude), 2)
                + (func.pow(69.1 * (self.longitude - longitude)
                   * func.cos(self.latitude / 57.3), 2))
            )
        )


class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String, nullable=False, unique=True)
    token_expiry = db.Column(db.DateTime, nullable=False, default=(
        lambda: datetime.utcnow() + timedelta(minutes=15)))


class DivePartnerAd(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    locality_id = db.Column(
        db.Integer, db.ForeignKey('locality.id'), nullable=True)
    area_two_id = db.Column(
        db.Integer, db.ForeignKey('area_two.id'), nullable=True)
    area_one_id = db.Column(
        db.Integer, db.ForeignKey('area_one.id'), nullable=True)
    country_id = db.Column(
        db.Integer, db.ForeignKey('country.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    country = db.relationship("Country", backref="dive_partner_ad")
    area_one = db.relationship("AreaOne", backref="dive_partner_ad")
    area_two = db.relationship("AreaTwo", backref="dive_partner_ad")
    locality = db.relationship("Locality", backref="dive_partner_ad")

    user = db.relationship("User", backref="dive_partner_ad")

    def get_dict(self):
        data = self.__dict__.copy()
        if data.get('_sa_instance_state'):
            data.pop('_sa_instance_state', None)
        return data
