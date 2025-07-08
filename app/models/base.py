"""
Base models and database setup.

This module contains the database instance and common utilities used across all models.
"""

from . import db

# Association table for many-to-many relationship between spots and tags
tags = db.Table(
    "tags",
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
    db.Column("spot_id", db.Integer, db.ForeignKey("spot.id"), primary_key=True),
)
