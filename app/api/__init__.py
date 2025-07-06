from flask import Blueprint


def init_app(app):
    """Initialize all API blueprints."""
    from app.api.auth import bp as auth_bp
    from app.api.dive_shops import bp as dive_shops_bp
    from app.api.health import bp as health_bp
    from app.api.locations import bp as locations_bp
    from app.api.reviews import bp as reviews_bp
    from app.api.search import bp as search_bp
    from app.api.spots import bp as spots_bp
    from app.api.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(spots_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(dive_shops_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(health_bp)