import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""

    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('FLASK_RUN_PORT', 8000))

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET')
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 2592000  # 30 days
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_SESSION_COOKIE = False

    # SQLAlchemy Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    def __init__(self):
        """Initialize configuration with proper database URL conversion."""
        # Silence SQLAlchemy 2.0 deprecation warnings
        os.environ.setdefault('SQLALCHEMY_SILENCE_UBER_WARNING', '1')

        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)

        self.SQLALCHEMY_DATABASE_URI = db_url

    # Cache Configuration
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    # Email Configuration
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

    # Google Services
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

    # Analytics
    AMPLITUDE_API_KEY = os.environ.get('AMPLITUDE_API_KEY')

    # Payment Processing
    STRIPE_PAYMENT_LINK = os.environ.get('STRIPE_PAYMENT_LINK')
    STRIPE_ENDPOINT_SECRET = os.environ.get('STRIPE_ENDPOINT_SECRET')

    # RevenueCat
    REVENUECAT_API_KEY = os.environ.get('REVENUECAT_API_KEY')

    # Apple Services
    APPLE_APP_ID = os.environ.get('APPLE_APP_ID')

    # Slack Webhooks
    SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK')
    SLACK_REVIEW_WEBHOOK = os.environ.get('SLACK_REVIEW_WEBHOOK')

    @property
    def JWT_COOKIE_SECURE(self):
        """Set JWT cookie secure based on debug mode."""
        return not self.DEBUG

    @classmethod
    def validate_required_vars(cls) -> list[str]:
        """Validate that all required environment variables are set."""
        required_vars = [
            'FLASK_SECRET_KEY',
            'DATABASE_URL',
            'JWT_SECRET',
        ]

        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)

        return missing_vars

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    CACHE_TYPE = "SimpleCache"

    def __init__(self):
        super().__init__()

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    CACHE_TYPE = "SimpleCache"  # Consider Redis for production

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    CACHE_TYPE = "SimpleCache"

    def __init__(self):
        test_db_url = os.environ.get('TEST_DATABASE_URL')
        if test_db_url:
            self.SQLALCHEMY_DATABASE_URI = test_db_url
        else:
            # Use SQLite in-memory for local tests if not specified
            self.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}