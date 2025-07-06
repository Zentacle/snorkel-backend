import os
from datetime import datetime

from amplitude import Amplitude, BaseEvent
from flask import Blueprint, current_app, jsonify

from app.extensions import cache, db

bp = Blueprint('health', __name__)


@bp.route('/')
def home():
    """Health check endpoint."""
    client = Amplitude(os.environ.get("AMPLITUDE_API_KEY"))
    client.configuration.min_id_length = 1
    event = BaseEvent(event_type="health_check", user_id="1")
    client.track(event)

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": {},
    }

    # Database check
    try:
        db.session.execute("SELECT 1")
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Cache check
    try:
        cache.set("health_check", "ok", timeout=10)
        cache_value = cache.get("health_check")
        if cache_value == "ok":
            health_status["checks"]["cache"] = "healthy"
        else:
            health_status["checks"]["cache"] = "unhealthy: cache not working"
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["cache"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # SendGrid check
    try:
        if os.environ.get("SENDGRID_API_KEY"):
            health_status["checks"]["sendgrid"] = "configured"
        else:
            health_status["checks"]["sendgrid"] = "not_configured"
    except Exception as e:
        health_status["checks"]["sendgrid"] = f"error: {str(e)}"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code


@bp.route('/ready')
def readiness_check():
    """Readiness check endpoint."""
    try:
        db.session.execute("SELECT 1")
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        return jsonify({"status": "not_ready", "error": str(e)}), 503


@bp.route('/live')
def liveness_check():
    """Liveness check endpoint."""
    return jsonify({"status": "alive"}), 200