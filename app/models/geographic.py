"""
Geographic models for location hierarchy.

This module contains models for geographic hierarchy including:
- GeographicNode: Flexible geographic hierarchy node
- Country: Country-level geographic entities
- AreaOne: State/province level geographic entities
- AreaTwo: County level geographic entities
- Locality: City/town level geographic entities
"""

from app.helpers.demicrosoft import demicrosoft

from . import db


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
