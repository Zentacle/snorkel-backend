from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_method

from app.helpers.demicrosoft import demicrosoft

db = SQLAlchemy()

tags = db.Table(
    "tags",
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
    db.Column("spot_id", db.Integer, db.ForeignKey("spot.id"), primary_key=True),
)


class GeographicNode(db.Model):
    """Flexible geographic hierarchy node that can represent any level"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False, unique=True)
    google_name = db.Column(db.String)
    google_place_id = db.Column(db.String)

    # Hierarchy relationships
    parent_id = db.Column(db.Integer, db.ForeignKey("geographic_node.id"), nullable=True)
    root_id = db.Column(db.Integer, db.ForeignKey("geographic_node.id"), nullable=True)

    # Geographic metadata
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    country_code = db.Column(db.String(2))  # ISO country code
    admin_level = db.Column(
        db.Integer,
        nullable=False,
    )  # 0=country, 1=state/province, 2=county, 3=city

    # Content
    description = db.Column(db.String)
    map_image_url = db.Column(db.String)

    # Legacy mapping fields for backwards compatibility
    legacy_country_id = db.Column(db.Integer, db.ForeignKey("country.id"), nullable=True)
    legacy_area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"), nullable=True)
    legacy_area_two_id = db.Column(db.Integer, db.ForeignKey("area_two.id"), nullable=True)
    legacy_locality_id = db.Column(db.Integer, db.ForeignKey("locality.id"), nullable=True)

    # Relationships
    parent = db.relationship("GeographicNode", remote_side=[id], foreign_keys=[parent_id], backref="children")
    root = db.relationship(
        "GeographicNode",
        remote_side=[id],
        foreign_keys=[root_id],
        backref="descendants",
    )
    spots = db.relationship("Spot", backref="geographic_node", lazy=True)
    shops = db.relationship(
        "DiveShop",
        backref="geographic_node",
        lazy=True,
        foreign_keys="DiveShop.geographic_node_id",
    )

    # Legacy relationships
    legacy_country = db.relationship("Country", foreign_keys=[legacy_country_id])
    legacy_area_one = db.relationship("AreaOne", foreign_keys=[legacy_area_one_id])
    legacy_area_two = db.relationship("AreaTwo", foreign_keys=[legacy_area_two_id])
    legacy_locality = db.relationship("Locality", foreign_keys=[legacy_locality_id])

    __table_args__ = (
        db.Index("ix_geographic_node_parent_id", "parent_id"),
        db.Index("ix_geographic_node_admin_level", "admin_level"),
        db.Index("ix_geographic_node_short_name_admin_level", "short_name", "admin_level"),
    )

    def get_legacy_url(self):
        """Generate the old-style URL for backwards compatibility"""
        if self.legacy_country and self.legacy_area_one and self.legacy_area_two and self.legacy_locality:
            return (
                f"/loc/{self.legacy_country.short_name}/"
                f"{self.legacy_area_one.short_name}/"
                f"{self.legacy_area_two.short_name}/"
                f"{self.legacy_locality.short_name}"
            )
        elif self.legacy_country and self.legacy_area_one and self.legacy_area_two:
            return (
                f"/loc/{self.legacy_country.short_name}/"
                f"{self.legacy_area_one.short_name}/"
                f"{self.legacy_area_two.short_name}"
            )
        elif self.legacy_country and self.legacy_area_one:
            return f"/loc/{self.legacy_country.short_name}/{self.legacy_area_one.short_name}"
        elif self.legacy_country:
            return f"/loc/{self.legacy_country.short_name}"
        return None

    def get_new_url(self):
        """Generate the new flexible URL"""
        path = self.get_path_to_root()
        return "/loc/" + "/".join([node.short_name for node in path])

    def get_url(self):
        """Return new URL, but can be overridden for legacy compatibility"""
        return self.get_new_url()

    def get_path_to_root(self):
        """Get ordered list from root to this node"""
        path = []
        current = self
        while current:
            path.insert(0, current)
            current = current.parent
        return path

    def get_ancestors(self):
        """Get all ancestors (excluding self)"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self, level=None):
        """Get all descendants, optionally filtered by level"""
        descendants = []
        for child in self.children:
            if level is None or child.admin_level == level:
                descendants.append(child)
            descendants.extend(child.get_descendants(level))
        return descendants

    def get_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "url": self.get_url(),
            "admin_level": self.admin_level,
            "country_code": self.country_code,
            "parent": self.parent.get_simple_dict() if self.parent else None,
            "num_spots": len(self.spots),
            "num_shops": len(self.shops),
        }

    def get_simple_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "admin_level": self.admin_level,
        }


class ShoreDivingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    name_url = db.Column(db.String)
    destination = db.Column(db.String)
    destination_url = db.Column(db.String)
    region = db.Column(db.String)
    region_url = db.Column(db.String)
    spot_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=False)

    spot = db.relationship("Spot", back_populates="shorediving_data", uselist=False)

    def get_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "url": self.get_url(),
        }

    def get_url(self):
        return "/Earth/" + self.region_url + "/" + self.destination_url + "/" + self.name_url

    def get_region_dict(self):
        return {
            "short_name": self.region,
            "name": self.region_url,
            "url": self.get_region_url(),
        }

    def get_region_url(self):
        return "/Earth/" + self.region_url + "/index.htm"

    def get_destination_dict(self):
        return {
            "short_name": self.destination,
            "name": self.destination_url,
            "url": self.get_destination_url(),
        }

    def get_destination_url(self):
        return "/Earth/" + self.region_url + "/" + self.destination_url + "/index.htm"

    @classmethod
    def create_url(cls, shorediving_data):
        return (
            "/Earth/"
            + shorediving_data.region_url
            + "/"
            + shorediving_data.destination_url
            + "/"
            + shorediving_data.name_url
        )


class ShoreDivingReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shorediving_id = db.Column(db.String, unique=True)
    shorediving_url = db.Column(db.String)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"))
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
            "shorediving_url": self.shorediving_url,
            "id": self.id,
            "shorediving_id": self.shorediving_id,
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
            data["profile_pic"] = "https://www.zentacle.com/image/profile_pic/placeholder"

        return data

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


# City


class Locality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_two_id = db.Column(db.Integer, db.ForeignKey("area_two.id"))
    area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"))
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    spots = db.relationship("Spot", backref="locality", lazy=True)
    shops = db.relationship("DiveShop", backref="locality", lazy=True)

    def get_dict(self, country=None, area_one=None, area_two=None):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        # Handle special cases
        if not data.get("short_name"):
            data["short_name"] = self.get_short_name()

        if country and area_one:
            data["url"] = self.get_url(country, area_one, area_two)
        elif hasattr(self, "country") and hasattr(self, "area_one") and self.country and self.area_one:
            data["url"] = self.get_url(self.country, self.area_one, self.area_two)

        return data

    def get_short_name(self):
        return self.short_name.lower() if self.short_name else demicrosoft(self.name).lower()

    def get_url(self, country, area_one, area_two):
        area_one_short_name = area_one.short_name if area_one else "_"
        return (
            "/loc/"
            + country.short_name
            + "/"
            + area_one_short_name
            + "/"
            + (area_two.short_name if area_two else "_")
            + "/"
            + self.get_short_name()
        )


# County - Doesn't always exist


class AreaTwo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"))
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    localities = db.relationship("Locality", backref="area_two", lazy=True)
    spots = db.relationship("Spot", backref="area_two", lazy=True)
    shops = db.relationship("DiveShop", backref="area_two", lazy=True)

    def get_simple_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
        }

    def get_dict(self, country=None, area_one=None):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        if country and area_one:
            data["url"] = self.get_url(country, area_one)
        elif hasattr(self, "country") and hasattr(self, "area_one") and self.country and self.area_one:
            data["url"] = self.get_url(self.country, self.area_one)

        return data

    def get_url(self, country, area_one):
        area_one_short_name = area_one.short_name if area_one else "_"
        return "/loc/" + country.short_name + "/" + area_one_short_name + "/" + self.short_name


# State


class AreaOne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_name = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"))
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True, nullable=False)
    map_image_url = db.Column(db.String)

    area_twos = db.relationship("AreaTwo", backref="area_one", lazy=True)
    localities = db.relationship("Locality", backref="area_one", lazy=True)
    spots = db.relationship("Spot", backref="area_one", lazy=True)
    shops = db.relationship("DiveShop", backref="area_one", lazy=True)

    def get_simple_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
        }

    def get_dict(self, country=None):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        if country:
            data["url"] = self.get_url(country)
        elif hasattr(self, "country") and self.country:
            data["url"] = self.get_url(self.country)

        return data

    def get_url(self, country):
        return "/loc/" + country.short_name + "/" + self.short_name


# Country


class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.String)
    url = db.Column(db.String, unique=True)
    map_image_url = db.Column(db.String)

    area_ones = db.relationship("AreaOne", backref="country", lazy=True)
    area_twos = db.relationship("AreaTwo", backref="country", lazy=True)
    localities = db.relationship("Locality", backref="country", lazy=True)
    spots = db.relationship("Spot", backref="country", lazy=True)
    shops = db.relationship("DiveShop", backref="country", lazy=True)

    def get_simple_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
        }

    def get_dict(self):
        data = {}
        # Get all column names from the model
        for column in self.__table__.columns:
            column_name = column.name
            # Get the value for this column
            value = getattr(self, column_name)
            data[column_name] = value

        data["url"] = self.get_url()
        return data

    def get_url(self):
        return "/loc/" + self.short_name


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


class WannaDiveData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=False)

    spot = db.relationship("Spot", back_populates="wannadive_data", uselist=False)


class DiveShop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    padi_store_id = db.Column(db.String, unique=True)
    name = db.Column(db.String)
    description = db.Column(db.String)
    auto_description = db.Column(db.String)
    description_v2 = db.Column(db.String)
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
    hero_img = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    location_google = db.Column(db.String)
    rating = db.Column(db.Float)
    num_reviews = db.Column(db.Integer)
    google_place_id = db.Column(db.String)
    padi_data = db.Column(db.JSON(none_as_null=True))

    username = db.Column(db.String)
    locality_id = db.Column(db.Integer, db.ForeignKey("locality.id"), nullable=True)
    area_two_id = db.Column(db.Integer, db.ForeignKey("area_two.id"), nullable=True)
    area_one_id = db.Column(db.Integer, db.ForeignKey("area_one.id"), nullable=True)
    country_id = db.Column(db.Integer, db.ForeignKey("country.id"), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    stamp_uri = db.Column(db.String, nullable=True)
    geographic_node_id = db.Column(db.Integer, db.ForeignKey("geographic_node.id"), nullable=True)
    owner = db.relationship("User", uselist=False)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        db.Index("ix_dive_shop_geographic_node_id", "geographic_node_id"),
        db.Index("ix_dive_shop_rating", "rating"),
        db.Index("ix_dive_shop_num_reviews", "num_reviews"),
        db.Index("ix_dive_shop_created", "created"),
    )

    def get_typeahead_dict(self):
        return {
            "id": self.id,
            "text": self.name,
            "subtext": f"{self.city}, {self.state}",
        }

    def get_simple_dict(self):
        simpleDict = {
            "id": self.id,
            "name": self.name,
            "website": self.website,
            "logo_img": self.logo_img,
            "fareharbor_url": self.fareharbor_url,
            "city": self.city,
            "state": self.state,
            "country_name": self.country_name,
            "address1": self.address1,
            "address2": self.address2,
            "zip": self.zip,
            "hero_img": self.hero_img if self.hero_img else self.logo_img,
            "rating": self.rating if self.rating else 0,
            "num_reviews": self.num_reviews if self.num_reviews else 0,
        }
        simpleDict["url"] = DiveShop.get_url(self)
        return simpleDict

    def get_dict(self):
        dict = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "website": self.website,
            "fareharbor_url": self.fareharbor_url,
            "logo_img": self.logo_img,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "state": self.state,
            "owner_user_id": self.owner_user_id,
            "stamp_uri": self.stamp_uri,
            "phone": self.phone,
            "description": (
                self.description
                if self.description
                else (self.description_v2 if self.description_v2 else self.auto_description)
            ),
            "hours": self.hours,
            "country_name": self.country_name,
            "zip": self.zip,
            "hero_img": self.hero_img if self.hero_img else self.logo_img,
            "rating": self.rating if self.rating else 0,
            "num_reviews": self.num_reviews if self.num_reviews else 0,
            "padi_data": self.padi_data,
        }

        dict["full_address"] = DiveShop.get_full_address(
            self.address1,
            self.address2,
            self.city,
            self.state,
            self.zip,
            self.country_name,
        )
        dict["url"] = DiveShop.get_url(self)
        if not dict["description"]:
            name = self.name
            city = str(self.city or "") + ", " + str(self.country_name or "")
            dict["description"] = (
                f"{name} is a scuba dive shop based in {city}. They are a PADI certified dive shop"
                "and offer a variety of dive and snorkel related services, gear, and guided tours."
            )
        return dict

    @classmethod
    def get_url(cls, shop):
        url_name = demicrosoft(shop.name).lower()
        id = shop.id
        return f"/shop/{id}/{url_name}"

    @classmethod
    def get_full_address(cls, address1, address2, city, state, zip, country):
        full_address = ""
        if address1:
            full_address += address1
        if address2:
            full_address += " " + address2
        if city:
            if full_address == "":
                full_address += city
            else:
                full_address += ", " + city
        if state:
            if full_address == "":
                full_address += state
            else:
                full_address += ", " + state
        if zip:
            full_address += " " + zip
        if country:
            if full_address == "":
                full_address += country
            else:
                full_address += ", " + country
        return full_address

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
        data = self.__dict__.copy()
        if data.get("_sa_instance_state"):
            data.pop("_sa_instance_state", None)
        return data


class ScheduledEmail(db.Model):
    """Model to track scheduled emails for Pro subscription automation"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    email_type = db.Column(db.String, nullable=False)  # 'welcome_pro', 'trial_reminder'
    scheduled_for = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    template_id = db.Column(db.String, nullable=False)
    dynamic_template_data = db.Column(db.JSON, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    user = db.relationship("User", backref="scheduled_emails")

    def get_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_type": self.email_type,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "template_id": self.template_id,
            "dynamic_template_data": self.dynamic_template_data,
            "created": self.created.isoformat() if self.created else None,
        }
