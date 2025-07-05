import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.models import User, Spot, Review, Country, AreaOne, AreaTwo, Locality


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    JWT_SECRET_KEY = 'test-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = False


@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    app = create_app(config_object=TestConfig)

    print(f"[TEST DEBUG] CI: {os.environ.get('CI')}")
    print(f"[TEST DEBUG] DATABASE_URL: {os.environ.get('DATABASE_URL')}")

    # Check if we're in CI environment (PostgreSQL) or local environment (SQLite)
    if os.environ.get('CI'):
        # Use PostgreSQL in CI environment
        print("[TEST DEBUG] Using PostgreSQL for CI")
        app.config.update({
            'TESTING': True,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'WTF_CSRF_ENABLED': False,
            'JWT_SECRET_KEY': 'test-secret-key',
            'JWT_ACCESS_TOKEN_EXPIRES': False,  # Disable token expiration for tests
        })
    else:
        # Use SQLite for local testing (regardless of DATABASE_URL)
        print("[TEST DEBUG] Using SQLite for local testing")
        db_fd, db_path = tempfile.mkstemp()
        app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'WTF_CSRF_ENABLED': False,
            'JWT_SECRET_KEY': 'test-secret-key',
            'JWT_ACCESS_TOKEN_EXPIRES': False,  # Disable token expiration for tests
        })
        print(f"[TEST DEBUG] SQLite path: {db_path}")
        print(f"[TEST DEBUG] Final SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    # Create the database and load test data
    with app.app_context():
        db.create_all()
        yield app

    # Clean up the temporary database (only for SQLite)
    if not os.environ.get('CI'):
        os.close(db_fd)
        os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """Create a fresh database session for a test."""
    with app.app_context():
        try:
            # Use the Flask app's database engine, not the global db.engine
            connection = db.engine.connect()
            transaction = connection.begin()

            # Create a session using the connection
            session = scoped_session(
                sessionmaker(bind=connection, binds={})
            )

            # Patch the db session
            db.session = session

            yield session

            # Clean up
            transaction.rollback()
            connection.close()
            session.remove()
        except Exception as e:
            print(f"Database connection error: {e}")
            print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
            raise


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        display_name='TestUser',
        username='testuser',
        password='hashed_password',
        admin=False,
        is_fake=False,
        unit='imperial'
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    user = User(
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        display_name='AdminUser',
        username='adminuser',
        password='hashed_password',
        admin=True,
        is_fake=False,
        unit='imperial'
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_country(db_session):
    """Create a sample country for testing."""
    country = Country(
        name='United States',
        short_name='us',
        description='United States of America',
        url='/us'
    )
    db_session.add(country)
    db_session.commit()
    return country


@pytest.fixture
def sample_area_one(db_session, sample_country):
    """Create a sample area one for testing."""
    area_one = AreaOne(
        name='California',
        short_name='ca',
        description='California State',
        url='/us/ca',
        country_id=sample_country.id
    )
    db_session.add(area_one)
    db_session.commit()
    return area_one


@pytest.fixture
def sample_area_two(db_session, sample_country, sample_area_one):
    """Create a sample area two for testing."""
    area_two = AreaTwo(
        name='Los Angeles County',
        short_name='la',
        description='Los Angeles County',
        url='/us/ca/la',
        country_id=sample_country.id,
        area_one_id=sample_area_one.id
    )
    db_session.add(area_two)
    db_session.commit()
    return area_two


@pytest.fixture
def sample_locality(db_session, sample_country, sample_area_one, sample_area_two):
    """Create a sample locality for testing."""
    locality = Locality(
        name='Santa Monica',
        short_name='santa-monica',
        description='Santa Monica Beach',
        url='/us/ca/la/santa-monica',
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
        area_two_id=sample_area_two.id
    )
    db_session.add(locality)
    db_session.commit()
    return locality


@pytest.fixture
def sample_spot(db_session, sample_locality):
    """Create a sample spot for testing."""
    spot = Spot(
        name='Santa Monica Beach',
        description='Beautiful beach for snorkeling',
        latitude=34.0195,
        longitude=-118.4912,
        locality_id=sample_locality.id,
        is_verified=True,
        is_deleted=False
    )
    db_session.add(spot)
    db_session.commit()
    return spot


@pytest.fixture
def sample_review(db_session, sample_user, sample_spot):
    """Create a sample review for testing."""
    review = Review(
        rating=5,
        text='Amazing snorkeling spot!',
        author_id=sample_user.id,
        beach_id=sample_spot.id,
        visibility=50,
        activity_type='snorkeling',
        title='Great Experience',
        is_private=False
    )
    db_session.add(review)
    db_session.commit()
    return review


@pytest.fixture
def auth_headers(sample_user):
    """Create authentication headers for testing."""
    from flask_jwt_extended import create_access_token

    token = create_access_token(identity=sample_user.id)
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def admin_auth_headers(admin_user):
    """Create admin authentication headers for testing."""
    from flask_jwt_extended import create_access_token

    token = create_access_token(identity=admin_user.id)
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def mock_amplitude():
    """Mock Amplitude analytics."""
    with patch('app.Amplitude') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    with patch('app.SendGridAPIClient') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_boto3():
    """Mock AWS Boto3 services."""
    with patch('app.boto3') as mock:
        mock_client = MagicMock()
        mock.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_requests():
    """Mock HTTP requests."""
    with patch('app.requests') as mock:
        yield mock


@pytest.fixture
def mock_cache():
    """Mock Flask-Caching."""
    with patch('app.cache') as mock:
        yield mock


# Test data factories
@pytest.fixture
def user_factory(db_session):
    """Factory for creating test users."""
    def _create_user(**kwargs):
        defaults = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'display_name': 'TestUser',
            'username': 'testuser',
            'password': 'hashed_password',
            'admin': False,
            'is_fake': False,
            'unit': 'imperial'
        }
        defaults.update(kwargs)

        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        return user

    return _create_user


@pytest.fixture
def spot_factory(db_session):
    """Factory for creating test spots."""
    def _create_spot(**kwargs):
        defaults = {
            'name': 'Test Spot',
            'description': 'Test spot description',
            'latitude': 34.0195,
            'longitude': -118.4912,
            'is_verified': True,
            'is_deleted': False
        }
        defaults.update(kwargs)

        spot = Spot(**defaults)
        db_session.add(spot)
        db_session.commit()
        return spot

    return _create_spot


@pytest.fixture
def review_factory(db_session):
    """Factory for creating test reviews."""
    def _create_review(**kwargs):
        defaults = {
            'rating': 5,
            'text': 'Test review',
            'visibility': 50,
            'activity_type': 'snorkeling',
            'title': 'Test Review',
            'is_private': False
        }
        defaults.update(kwargs)

        review = Review(**defaults)
        db_session.add(review)
        db_session.commit()
        return review

    return _create_review