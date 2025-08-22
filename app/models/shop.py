"""
Shop-related models.

This module contains models related to shop entities:
- DiveShop: Dive shop information and services
- DivePartnerAd: Dive partner advertisements
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_method

from app.helpers.demicrosoft import demicrosoft

from . import db


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
