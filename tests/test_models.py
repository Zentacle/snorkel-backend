import pytest
from datetime import datetime, timedelta
from app.models import User, Spot, Review, Country, AreaOne, AreaTwo, Locality, Image, Tag


class TestUser:
    """Test cases for User model."""

    def test_user_creation(self, db_session):
        """Test creating a new user."""
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

        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.first_name == 'Test'
        assert user.last_name == 'User'
        assert user.display_name == 'TestUser'
        assert user.username == 'testuser'
        assert user.admin is False
        assert user.is_fake is False
        assert user.unit == 'imperial'

    def test_user_get_dict(self, sample_user):
        """Test user get_dict method."""
        user_dict = sample_user.get_dict()
        # Check that sensitive fields are removed
        assert 'password' not in user_dict
        assert 'email' not in user_dict
        assert 'admin' not in user_dict
        assert 'is_fake' not in user_dict
        assert 'latitude' not in user_dict
        assert 'longitude' not in user_dict
        assert 'push_token' not in user_dict

        # Check that required fields are present
        assert user_dict['id'] == sample_user.id
        assert user_dict['first_name'] == 'Test'
        assert user_dict['last_name'] == 'User'
        assert user_dict['display_name'] == 'TestUser'
        assert user_dict['username'] == 'testuser'
        assert user_dict['unit'] == 'imperial'

        # Check default values
        assert user_dict['bio'] == 'Looking for a dive buddy!'
        assert user_dict['profile_pic'] == 'https://www.zentacle.com/image/profile_pic/placeholder'

    def test_user_distance_calculation(self, sample_user):
        """Test user distance calculation."""
        # Set user coordinates
        sample_user.latitude = 34.0195
        sample_user.longitude = -118.4912

        # Calculate distance to a nearby point
        distance = sample_user.distance(34.0195, -118.4913)

        assert isinstance(distance, float)
        assert distance > 0

    def test_user_username_lowercase(self, db_session):
        """Test that username is stored in lowercase."""
        user = User(
            email='test@example.com',
            username='TestUser',
            password='hashed_password'
        )
        db_session.add(user)
        db_session.commit()

        user_dict = user.get_dict()
        assert user_dict['username'] == 'testuser'


class TestSpot:
    """Test cases for Spot model."""

    def test_spot_creation(self, db_session, sample_locality):
        """Test creating a new spot."""
        spot = Spot(
            name='Test Beach',
            description='A beautiful beach for snorkeling',
            latitude=34.0195,
            longitude=-118.4912,
            locality_id=sample_locality.id,
            is_verified=True,
            is_deleted=False
        )
        db_session.add(spot)
        db_session.commit()

        assert spot.id is not None
        assert spot.name == 'Test Beach'
        assert spot.description == 'A beautiful beach for snorkeling'
        assert spot.latitude == 34.0195
        assert spot.longitude == -118.4912
        assert spot.is_verified is True
        assert spot.is_deleted is False

    def test_spot_get_dict(self, sample_spot):
        """Test spot get_dict method."""
        spot_dict = sample_spot.get_dict()

        assert spot_dict['id'] == sample_spot.id
        assert spot_dict['name'] == 'Santa Monica Beach'
        assert spot_dict['description'] == 'Beautiful beach for snorkeling'
        assert spot_dict['latitude'] == 34.0195
        assert spot_dict['longitude'] == -118.4912
        assert spot_dict['is_verified'] is True
        assert spot_dict['is_deleted'] is False

    def test_spot_get_simple_dict(self, sample_spot):
        """Test spot get_simple_dict method."""
        simple_dict = sample_spot.get_simple_dict()

        assert simple_dict['id'] == sample_spot.id
        assert simple_dict['name'] == 'Santa Monica Beach'
        assert 'hero_img' in simple_dict
        assert 'rating' in simple_dict
        assert 'num_reviews' in simple_dict
        assert 'location_city' in simple_dict

    def test_spot_distance_calculation(self, sample_spot):
        """Test spot distance calculation."""
        distance = sample_spot.distance(34.0195, -118.4913)

        assert isinstance(distance, float)
        assert distance > 0

    def test_spot_url_creation(self, sample_spot):
        """Test spot URL creation."""
        url = Spot.create_url(sample_spot.id, sample_spot.name)
        expected_url = f'/Beach/{sample_spot.id}/{sample_spot.name.lower().replace(" ", "-")}'
        assert url == expected_url


class TestReview:
    """Test cases for Review model."""

    def test_review_creation(self, db_session, sample_user, sample_spot):
        """Test creating a new review."""
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

        assert review.id is not None
        assert review.rating == 5
        assert review.text == 'Amazing snorkeling spot!'
        assert review.author_id == sample_user.id
        assert review.beach_id == sample_spot.id
        assert review.visibility == 50
        assert review.activity_type == 'snorkeling'
        assert review.title == 'Great Experience'
        assert review.is_private is False

    def test_review_get_dict(self, sample_review):
        """Test review get_dict method."""
        review_dict = sample_review.get_dict()

        assert review_dict['id'] == sample_review.id
        assert review_dict['rating'] == 5
        assert review_dict['text'] == 'Amazing snorkeling spot!'
        assert review_dict['visibility'] == 50
        assert review_dict['activity_type'] == 'snorkeling'
        assert review_dict['title'] == 'Great Experience'
        assert review_dict['is_private'] is False

    def test_review_get_simple_dict(self, sample_review):
        """Test review get_simple_dict method."""
        simple_dict = sample_review.get_simple_dict()

        assert simple_dict['id'] == sample_review.id
        assert simple_dict['rating'] == 5
        assert simple_dict['text'] == 'Amazing snorkeling spot!'
        assert 'date_dived' in simple_dict
        assert 'date_posted' in simple_dict
        assert 'activity_type' in simple_dict
        assert 'title' in simple_dict
        assert 'is_private' in simple_dict


class TestCountry:
    """Test cases for Country model."""

    def test_country_creation(self, db_session):
        """Test creating a new country."""
        country = Country(
            name='United States',
            short_name='us',
            description='United States of America',
            url='/us'
        )
        db_session.add(country)
        db_session.commit()

        assert country.id is not None
        assert country.name == 'United States'
        assert country.short_name == 'us'
        assert country.description == 'United States of America'
        assert country.url == '/us'

    def test_country_get_dict(self, sample_country):
        """Test country get_dict method."""
        country_dict = sample_country.get_dict()

        assert country_dict['id'] == sample_country.id
        assert country_dict['name'] == 'United States'
        assert country_dict['short_name'] == 'us'
        assert country_dict['description'] == 'United States of America'
        assert country_dict['url'] == '/loc/us'

    def test_country_get_simple_dict(self, sample_country):
        """Test country get_simple_dict method."""
        simple_dict = sample_country.get_simple_dict()

        assert simple_dict['id'] == sample_country.id
        assert simple_dict['name'] == 'United States'
        assert simple_dict['short_name'] == 'us'


class TestAreaOne:
    """Test cases for AreaOne model."""

    def test_area_one_creation(self, db_session, sample_country):
        """Test creating a new area one."""
        area_one = AreaOne(
            name='California',
            short_name='ca',
            description='California State',
            url='/us/ca',
            country_id=sample_country.id
        )
        db_session.add(area_one)
        db_session.commit()

        assert area_one.id is not None
        assert area_one.name == 'California'
        assert area_one.short_name == 'ca'
        assert area_one.description == 'California State'
        assert area_one.url == '/us/ca'
        assert area_one.country_id == sample_country.id

    def test_area_one_get_dict(self, sample_area_one, sample_country):
        """Test area one get_dict method."""
        area_dict = sample_area_one.get_dict(country=sample_country)

        assert area_dict['id'] == sample_area_one.id
        assert area_dict['name'] == 'California'
        assert area_dict['short_name'] == 'ca'
        assert area_dict['description'] == 'California State'
        assert area_dict['url'] == '/loc/us/ca'

    def test_area_one_get_simple_dict(self, sample_area_one):
        """Test area one get_simple_dict method."""
        simple_dict = sample_area_one.get_simple_dict()

        assert simple_dict['id'] == sample_area_one.id
        assert simple_dict['name'] == 'California'
        assert simple_dict['short_name'] == 'ca'


class TestAreaTwo:
    """Test cases for AreaTwo model."""

    def test_area_two_creation(self, db_session, sample_country, sample_area_one):
        """Test creating a new area two."""
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

        assert area_two.id is not None
        assert area_two.name == 'Los Angeles County'
        assert area_two.short_name == 'la'
        assert area_two.description == 'Los Angeles County'
        assert area_two.url == '/us/ca/la'
        assert area_two.country_id == sample_country.id
        assert area_two.area_one_id == sample_area_one.id

    def test_area_two_get_dict(self, sample_area_two, sample_country, sample_area_one):
        """Test area two get_dict method."""
        area_dict = sample_area_two.get_dict(country=sample_country, area_one=sample_area_one)

        assert area_dict['id'] == sample_area_two.id
        assert area_dict['name'] == 'Los Angeles County'
        assert area_dict['short_name'] == 'la'
        assert area_dict['description'] == 'Los Angeles County'
        assert area_dict['url'] == '/loc/us/ca/la'


class TestLocality:
    """Test cases for Locality model."""

    def test_locality_creation(self, db_session, sample_country, sample_area_one, sample_area_two):
        """Test creating a new locality."""
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

        assert locality.id is not None
        assert locality.name == 'Santa Monica'
        assert locality.short_name == 'santa-monica'
        assert locality.description == 'Santa Monica Beach'
        assert locality.url == '/us/ca/la/santa-monica'
        assert locality.country_id == sample_country.id
        assert locality.area_one_id == sample_area_one.id
        assert locality.area_two_id == sample_area_two.id

    def test_locality_get_dict(self, sample_locality, sample_country, sample_area_one, sample_area_two):
        """Test locality get_dict method."""
        locality_dict = sample_locality.get_dict(country=sample_country, area_one=sample_area_one, area_two=sample_area_two)

        assert locality_dict['id'] == sample_locality.id
        assert locality_dict['name'] == 'Santa Monica'
        assert locality_dict['short_name'] == 'santa-monica'
        assert locality_dict['description'] == 'Santa Monica Beach'
        assert locality_dict['url'] == '/loc/us/ca/la/santa-monica'


class TestImage:
    """Test cases for Image model."""

    def test_image_creation(self, db_session, sample_user, sample_spot):
        """Test creating a new image."""
        image = Image(
            url='https://example.com/image.jpg',
            beach_id=sample_spot.id,
            user_id=sample_user.id,
            caption='Beautiful beach photo'
        )
        db_session.add(image)
        db_session.commit()

        assert image.id is not None
        assert image.url == 'https://example.com/image.jpg'
        assert image.beach_id == sample_spot.id
        assert image.user_id == sample_user.id
        assert image.caption == 'Beautiful beach photo'

    def test_image_get_dict(self, db_session, sample_user, sample_spot):
        """Test image get_dict method."""
        image = Image(
            url='https://example.com/image.jpg',
            beach_id=sample_spot.id,
            user_id=sample_user.id,
            caption='Beautiful beach photo'
        )
        db_session.add(image)
        db_session.commit()

        image_dict = image.get_dict()

        assert image_dict['id'] == image.id
        assert image_dict['url'] == 'https://example.com/image.jpg'
        assert image_dict['beach_id'] == sample_spot.id
        assert image_dict['user_id'] == sample_user.id
        assert image_dict['caption'] == 'Beautiful beach photo'


class TestTag:
    """Test cases for Tag model."""

    def test_tag_creation(self, db_session):
        """Test creating a new tag."""
        tag = Tag(
            text='Coral Reef',
            type='marine_life',
            short_name='coral-reef'
        )
        db_session.add(tag)
        db_session.commit()

        assert tag.id is not None
        assert tag.text == 'Coral Reef'
        assert tag.type == 'marine_life'
        assert tag.short_name == 'coral-reef'

    def test_tag_get_dict(self, db_session):
        """Test tag get_dict method."""
        tag = Tag(
            text='Coral Reef',
            type='marine_life',
            short_name='coral-reef'
        )
        db_session.add(tag)
        db_session.commit()

        tag_dict = tag.get_dict()

        assert tag_dict['id'] == tag.id
        assert tag_dict['text'] == 'Coral Reef'
        assert tag_dict['type'] == 'marine_life'
        assert tag_dict['short_name'] == 'coral-reef'