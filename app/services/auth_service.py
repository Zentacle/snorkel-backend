from datetime import datetime, timedelta

import bcrypt
import jwt
import requests
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.user import User


class AuthService:
    """Service class for handling authentication business logic."""

    @staticmethod
    def create_user(first_name, last_name, email, username=None, profile_pic=None,
                   password=None, phone=None, app_name=None):
        """Create a new user account."""
        display_name = f"{first_name} {last_name}"

        # Check if user already exists
        existing_user = User.query.filter(
            func.lower(User.email) == email.lower()
        ).first()

        if existing_user:
            return {"error": "User already exists"}, 400

        # Create new user
        user = User(
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            email=email,
            username=username,
            profile_pic=profile_pic,
            phone=phone
        )

        # Hash password if provided
        if password:
            user.password = bcrypt.hashpw(
                password.encode('utf-8'), bcrypt.gensalt()
            ).decode('utf-8')

        db.session.add(user)
        db.session.commit()

        return AuthService._create_auth_response(user)

    @staticmethod
    def authenticate_user(email, password):
        """Authenticate user with email and password."""
        user = User.query.filter(
            func.lower(User.email) == email.lower()
        ).first()

        if not user or not user.password:
            return {"error": "Invalid credentials"}, 401

        if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            return {"error": "Invalid credentials"}, 401

        return AuthService._create_auth_response(user)

    @staticmethod
    def authenticate_google_user(id_token_str):
        """Authenticate user with Google ID token."""
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                current_app.config['GOOGLE_CLIENT_ID']
            )

            email = idinfo['email']
            user = User.query.filter(func.lower(User.email) == email.lower()).first()

            if not user:
                # Create new user from Google data
                user = User(
                    email=email,
                    first_name=idinfo.get('given_name', ''),
                    last_name=idinfo.get('family_name', ''),
                    display_name=idinfo.get('name', email),
                    profile_pic=idinfo.get('picture')
                )
                db.session.add(user)
                db.session.commit()

            return AuthService._create_auth_response(user)

        except Exception as e:
            return {"error": f"Google authentication failed: {str(e)}"}, 401

    @staticmethod
    def authenticate_apple_user(id_token_str, audience=None):
        """Authenticate user with Apple ID token."""
        try:
            audience = audience or current_app.config['APPLE_APP_ID']

            # Get Apple's public keys
            key_payload = requests.get("https://appleid.apple.com/auth/keys").json()
            token_headers = jwt.get_unverified_header(id_token_str)

            # Find matching key
            jwk = None
            for key in key_payload["keys"]:
                if key.get("kid") == token_headers.get("kid"):
                    jwk = key
                    break

            if not jwk:
                return {"error": "No matching key found"}, 500

            public_key = RSAAlgorithm.from_jwk(jwt.dumps(jwk))

            # Verify token
            token = jwt.decode(
                id_token_str, public_key, audience=audience, algorithms=["RS256"]
            )

            email = token.get("email")
            if not email:
                return {"error": "No email in token"}, 400

            user = User.query.filter(func.lower(User.email) == email.lower()).first()

            if not user:
                # Create new user from Apple data
                user = User(
                    email=email,
                    first_name=email.split('@')[0],  # Fallback
                    display_name=email
                )
                db.session.add(user)
                db.session.commit()

            return AuthService._create_auth_response(user)

        except jwt.exceptions.ExpiredSignatureError:
            return {"error": "Token has expired"}, 401
        except jwt.exceptions.InvalidAudienceError:
            return {"error": "Invalid audience"}, 401
        except Exception as e:
            return {"error": f"Apple authentication failed: {str(e)}"}, 401

    @staticmethod
    def _create_auth_response(user):
        """Create authentication response with tokens."""
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return {
            "user": user.get_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token
        }, 200

    @staticmethod
    def update_user_profile(user_id, **kwargs):
        """Update user profile information."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}, 404

        # Update allowed fields
        allowed_fields = [
            'first_name', 'last_name', 'display_name', 'username',
            'profile_pic', 'hometown', 'unit', 'bio', 'phone',
            'certification', 'latitude', 'longitude'
        ]

        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(user, field, value)

        db.session.commit()
        return {"user": user.get_dict()}, 200