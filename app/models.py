from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=False, nullable=False)
    display_name = db.Column(db.String)
    username = db.Column(db.String)
    profile_pic = db.Column(db.String)

    reviews = db.relationship("Review")
    images = db.relationship("Image")

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
    visibility = db.Column(db.Integer, nullable=True) # in meters
    activity_type = db.Column(db.String)

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)