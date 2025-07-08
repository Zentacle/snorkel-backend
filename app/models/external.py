"""
External data models.

This module contains models for data imported from external sources:
- ShoreDivingData: Data imported from ShoreDiving.com
- ShoreDivingReview: Review data from ShoreDiving.com
- WannaDiveData: Data imported from WannaDive.net
"""

from . import db


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


class WannaDiveData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=False)

    spot = db.relationship("Spot", back_populates="wannadive_data", uselist=False)
