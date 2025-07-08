"""
Models package for the Snorkel Backend application.

This package contains all database models organized by domain:
- base: Database setup and common utilities
- geographic: Geographic hierarchy models (GeographicNode, Country, AreaOne, etc.)
- user: User-related models (User, PasswordReset, etc.)
- dive: Dive-related models (Spot, Review, Image, etc.)
- shop: Shop-related models (DiveShop, DivePartnerAd, etc.)
- external: External data models (ShoreDivingData, WannaDiveData, etc.)
- system: System models (ScheduledEmail, etc.)
"""

from flask_sqlalchemy import SQLAlchemy

# Initialize the database instance
db = SQLAlchemy()

# Import all models to ensure they are registered with SQLAlchemy
from .base import tags
from .dive import Image, Review, Spot, Tag
from .external import ShoreDivingData, ShoreDivingReview, WannaDiveData
from .geographic import AreaOne, AreaTwo, Country, GeographicNode, Locality
from .shop import DivePartnerAd, DiveShop
from .system import ScheduledEmail
from .user import PasswordReset, User

# Export all models for easy importing
__all__ = [
    # Database instance
    "db",
    # Base
    "tags",
    # Geographic models
    "GeographicNode",
    "Country",
    "AreaOne",
    "AreaTwo",
    "Locality",
    # User models
    "User",
    "PasswordReset",
    # Dive models
    "Spot",
    "Review",
    "Image",
    "Tag",
    # Business models
    "DiveShop",
    "DivePartnerAd",
    # External data models
    "ShoreDivingData",
    "ShoreDivingReview",
    "WannaDiveData",
    # System models
    "ScheduledEmail",
]
