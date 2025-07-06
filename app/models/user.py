from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_method

from app.extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    display_name = db.Column(db.String)
    username = db.Column(db.String, unique=True)
    profile_pic = db.Column(db.String)
    password = db.Column(db.String)
    registered_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hometown = db.Column(db.String)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    is_fake = db.Column(db.Boolean, default=False)
    unit = db.Column(db.String, nullable=False, default="imperial")
    bio = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    has_pro = db.Column(db.Boolean, default=False)
    push_token = db.Column(db.String)
    phone = db.Column(db.String)
    certification = db.Column(db.String)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    reviews = db.relationship(
        "Review",
        backref=db.backref("user", lazy=True),
        order_by="asc(Review.date_dived)",
    )
    images = db.relationship("Image")

    def get_dict(self):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Skip sensitive fields
            if column_name in [
                "password",
                "email",
                "admin",
                "is_fake",
                "latitude",
                "longitude",
                "push_token",
            ]:
                continue
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        # Apply any transformations
        if data.get("username"):
            data["username"] = data["username"].lower()

        # Set defaults for missing fields
        if not data.get("bio"):
            data["bio"] = "Looking for a dive buddy!"
        if not data.get("profile_pic"):
            data["profile_pic"] = (
                "https://www.zentacle.com/image/profile_pic/placeholder"
            )

        return data

    @hybrid_method
    def distance(self, latitude, longitude):
        import math

        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + (
                    (
                        69.1
                        * (self.longitude - longitude)
                        * math.cos(self.latitude / 57.3)
                    )
                    ** 2
                )
            )
        )

    @distance.expression
    def distance(self, latitude, longitude):
        import math

        return func.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + (
                    (
                        69.1
                        * (self.longitude - longitude)
                        * func.cos(self.latitude / 57.3)
                    )
                    ** 2
                )
            )
        )


class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String, nullable=False, unique=True)
    token_expiry = db.Column(
        db.DateTime,
        nullable=False,
        default=(lambda: datetime.utcnow() + timedelta(minutes=15)),
    )
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    user = db.relationship("User", backref="password_resets")


class DivePartnerAd(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    locality_id = db.Column(db.Integer, db.ForeignKey("locality.id"), nullable=True)
    area_two_id = db.Column(db.Integer, db.ForeignKey("area_two.id"), nullable=True)
    area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    country = db.relationship("Country", backref="dive_partner_ad")
    area_one = db.relationship("AreaOne", backref="dive_partner_ad")
    area_two = db.relationship("AreaTwo", backref="dive_partner_ad")
    locality = db.relationship("Locality", backref="dive_partner_ad")

    user = db.relationship("User", backref="dive_partner_ad")

    def get_dict(self):
        return {
            "id": self.id,
            "user": self.user.get_dict() if self.user else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }