from __future__ import print_function

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import newrelic.agent
from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.config import config
from app.extensions import cache, cors, db, jwt_manager, migrate

# Load environment variables
load_dotenv()


def create_app(config_name=None, config_object=None):
    """Application factory pattern."""
    if config_object is not None:
        app_config = config_object
    else:
        config_name = config_name or os.environ.get("FLASK_ENV", "development")
        app_config_class = config.get(config_name, config["default"])
        app_config = app_config_class()

    app = Flask(__name__)
    app.config.from_object(app_config)

    # Set up logging
    if __name__ != "__main__":
        gunicorn_logger = logging.getLogger("gunicorn.error")
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    # Initialize extensions
    cors.init_app(app)
    cache.init_app(app)
    jwt_manager.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # JWT user loader
    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        from app.models.user import User
        user_id = jwt_data["sub"]
        return User.query.filter_by(id=user_id).one_or_none()

    # Register blueprints
    from app.api import init_app as init_api
    init_api(app)

    # Register middleware and error handlers
    register_middleware(app)
    register_error_handlers(app)

    return app


def register_middleware(app):
    """Register application middleware."""

    @app.after_request
    def refresh_expiring_jwts(response):
        """Refresh JWT tokens if they're about to expire."""
        try:
            from flask_jwt_extended import (
                create_access_token,
                get_jwt,
                get_jwt_identity,
                set_access_cookies,
            )
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            return response

    @app.before_request
    def capture_request_params():
        """Capture request parameters for monitoring."""
        if not app.config.get("DEBUG", False):
            newrelic.agent.capture_request_params()


def register_error_handlers(app):
    """Register error handlers."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle HTTP exceptions."""
        response = e.get_response()
        response.data = json.dumps({
            "code": e.code,
            "name": e.name,
            "msg": e.description,
        })
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        """Handle unhandled exceptions."""
        newrelic.agent.record_exception(e)
        app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        response = jsonify({
            "code": 500,
            "name": "Internal Server Error",
            "msg": "An unexpected error occurred. Please try again later.",
        })
        response.status_code = 500
        return response
