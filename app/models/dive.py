"""
Dive-related models.

This module contains models related to dive spots, reviews, and content:
- Spot: Dive spot/location information
- Review: User reviews of dive spots
- Image: Images associated with spots and reviews
- Tag: Tags for categorizing spots
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_method

from app.helpers.demicrosoft import demicrosoft

from . import db
from .base import tags


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
    submitter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    google_place_id = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    difficulty = db.Column(db.String)
    locality_id = db.Column(db.Integer, db.ForeignKey("locality.id"), nullable=True)
    area_two_id = db.Column(db.Integer, db.ForeignKey("area_two.id"), nullable=True)
    area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"), nullable=True)
    noaa_station_id = db.Column(db.String)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )
    geographic_node_id = db.Column(db.Integer, db.ForeignKey("geographic_node.id"), nullable=True)

    reviews = db.relationship("Review", backref="spot")
    images = db.relationship("Image", backref="spot")
    submitter = db.relationship("User", uselist=False)
    shorediving_data = db.relationship("ShoreDivingData", back_populates="spot", uselist=False)
    wannadive_data = db.relationship("WannaDiveData", back_populates="spot", uselist=False)
    tags = db.relationship("Tag", secondary=tags, lazy="subquery", backref=db.backref("spot", lazy=True))

    __table_args__ = (
        db.Index("ix_spot_geographic_node_id", "geographic_node_id"),
        db.Index("ix_spot_geographic_verified_deleted", "geographic_node_id", "is_verified", "is_deleted"),
        db.Index("ix_spot_num_reviews", "num_reviews"),
        db.Index("ix_spot_rating", "rating"),
        db.Index("ix_spot_last_review_date", "last_review_date"),
    )

    def get_simple_dict(self):
        data = {}
        keys = [
            "id",
            "name",
            "hero_img",
            "rating",
            "num_reviews",
            "location_city",
        ]
        for key in keys:
            data[key] = getattr(self, key)
        data["url"] = self.get_url()
        return data

    def get_dict(self):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        # Handle special cases
        if data.get("shorediving_data"):
            data.pop("shorediving_data", None)

        # Set default description if missing or empty
        if not data.get("description") or not data.get("description").strip():
            data["description"] = (
                f"{data.get('name')} is a {data.get('rating') if data.get('rating') else 0}-star"
                f" rated scuba dive and snorkel destination in {data.get('location_city')} which is accessible from"
                f" shore based on {data.get('num_reviews')} ratings."
            )

        if not data.get("difficulty"):
            data["difficulty"] = "Unrated"

        # Handle tags
        if hasattr(self, "tags") and self.tags:
            data["access"] = []
            for tag in self.tags:
                data["access"].append(tag.get_dict())

        data["url"] = "/Beach/" + str(self.id) + "/" + demicrosoft(self.name).lower()
        return data

    def get_url(self):
        """Get the new geographic-based URL if available, otherwise fall back to legacy"""
        if self.geographic_node:
            # New format: /loc/country/state/city/spot-name-id
            path = self.geographic_node.get_path_to_root()
            url_parts = [node.short_name for node in path]
            # Add spot with name-id for SEO and uniqueness
            url_parts.append(f"{self.get_beach_name_for_url()}-{self.id}")
            return "/loc/" + "/".join(url_parts)
        else:
            # Legacy format: /Beach/id/name
            return Spot.create_legacy_url(self.id, self.name)

    def get_legacy_url(self):
        """Get the legacy URL format for backwards compatibility"""
        return Spot.create_legacy_url(self.id, self.name)

    def get_beach_name_for_url(self):
        return demicrosoft(self.name).lower()

    @classmethod
    def create_legacy_url(cls, id, name):
        return "/Beach/" + str(id) + "/" + demicrosoft(name).lower()

    @classmethod
    def create_url(cls, id, name):
        """Legacy method for backwards compatibility"""
        return cls.create_legacy_url(id, name)

    @hybrid_method
    def get_confidence_score(self):
        import math

        z = 1.645  # 90% confidence interval (could 1.960 for 95%)
        std_dev = 0.50  # roughly calculated based on existing review data
        if self.num_reviews:
            return float(self.rating) - z * (std_dev / math.sqrt(self.num_reviews))
        else:
            return 0

    @get_confidence_score.expression
    def get_confidence_score(self):
        """Database expression for confidence score calculation"""
        z = 1.645  # 90% confidence interval
        std_dev = 0.50  # standard deviation

        # Convert rating to float and handle nulls
        rating_float = func.cast(self.rating, db.Float)

        # Calculate confidence score: rating - z * (std_dev / sqrt(num_reviews))
        # Handle case where num_reviews is 0 or null
        confidence_score = func.case(
            (
                self.num_reviews > 0,
                rating_float - z * (std_dev / func.sqrt(func.cast(self.num_reviews, db.Float))),
            ),
            else_=0.0,
        )

        return confidence_score

    @hybrid_method
    def distance(self, latitude, longitude):
        import math

        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude) * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @distance.expression
    def distance(self, latitude, longitude):
        return func.sqrt(
            (
                func.pow(69.1 * (self.latitude - latitude), 2)
                + (
                    func.pow(
                        69.1 * (self.longitude - longitude) * func.cos(self.latitude / 57.3),
                        2,
                    )
                )
            )
        )

    @hybrid_method
    def sqlite3_distance(self, latitude, longitude):
        import math

        return math.sqrt(
            (
                69.1 * (self.latitude - latitude) ** 2
                + ((69.1 * (self.longitude - longitude) * math.cos(self.latitude / 57.3)) ** 2)
            )
        )

    @sqlite3_distance.expression
    def sqlite3_distance(self, latitude, longitude):
        return func.abs(
            (69.1 * (self.latitude - latitude) * 69.1 * (self.latitude - latitude))
            + ((69.1 * (self.longitude - longitude)) * (69.1 * (self.longitude - longitude)))
        )


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    beach_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=False)
    visibility = db.Column(db.Integer, nullable=True)  # in ft
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_dived = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
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
    dive_shop_id = db.Column(db.Integer, db.ForeignKey("dive_shop.id"))
    is_private = db.Column(db.Boolean, nullable=True, default=False)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    dive_shop = db.relationship("DiveShop", backref="reviews", uselist=False)
    images = db.relationship("Image", backref=db.backref("review", lazy=True))
    shorediving_data = db.relationship("ShoreDivingReview", back_populates="review", uselist=False)

    def get_simple_dict(self):
        keys = [
            "id",
            "rating",
            "text",
            "date_dived",
            "date_posted",
            "activity_type",
            "title",
            "is_private",
        ]
        data = {}
        for key in keys:
            data[key] = getattr(self, key)
        return data

    def get_dict(self):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        # Handle special cases
        if not data.get("title") and hasattr(self, "spot") and self.spot and self.spot.name:
            data["title"] = self.spot.name

        # Remove relationship objects that shouldn't be serialized
        if data.get("spot"):
            data.pop("spot", None)

        return data


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=False, nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=True)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    caption = db.Column(db.String)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def get_dict(self):
        return {
            "url": self.url,
            "id": self.id,
            "beach_id": self.beach_id,
            "user_id": self.user_id,
            "review_id": self.review_id,
            "caption": self.caption,
        }


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, unique=True, nullable=False)

    def get_dict(self):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        return data
