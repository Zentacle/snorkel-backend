# Project Restructuring Guide

This guide outlines the new MVC-like architecture for the snorkel-backend project and how to migrate from the current structure.

## New Architecture Overview

The new structure follows a clean separation of concerns with the following layers:

### 1. **Models Layer** (`app/models/`)
- **Purpose**: Database models and data access
- **Files**:
  - `user.py` - User, PasswordReset, DivePartnerAd models
  - `spot.py` - Spot, ShoreDivingData, ShoreDivingReview, WannaDiveData models
  - `review.py` - Review model
  - `image.py` - Image model
  - `location.py` - Country, AreaOne, AreaTwo, Locality models
  - `dive_shop.py` - DiveShop model
  - `tag.py` - Tag model and association table

### 2. **Services Layer** (`app/services/`)
- **Purpose**: Business logic and data processing
- **Files**:
  - `auth_service.py` - Authentication and user management
  - `user_service.py` - User-related business logic
  - `spot_service.py` - Spot-related business logic
  - `review_service.py` - Review-related business logic
  - `location_service.py` - Location-related business logic
  - `notification_service.py` - Push notifications and emails
  - `payment_service.py` - Payment processing
  - `file_service.py` - File uploads and S3 operations

### 3. **API Layer** (`app/api/`)
- **Purpose**: HTTP endpoints and request/response handling
- **Files**:
  - `auth.py` - Authentication endpoints
  - `users.py` - User management endpoints
  - `spots.py` - Spot-related endpoints
  - `reviews.py` - Review-related endpoints
  - `locations.py` - Location-related endpoints
  - `dive_shops.py` - Dive shop endpoints
  - `search.py` - Search functionality
  - `health.py` - Health check endpoints

### 4. **Utils Layer** (`app/utils/`)
- **Purpose**: Utility functions and helpers
- **Files**:
  - `validators.py` - Input validation functions
  - `formatters.py` - Data formatting functions
  - `decorators.py` - Custom decorators
  - `helpers.py` - General helper functions

### 5. **Extensions** (`app/extensions.py`)
- **Purpose**: Flask extension initialization
- **Contains**: db, cors, cache, jwt_manager, migrate

## Migration Steps

### Step 1: Complete Model Separation

1. **Extract remaining models** from `app/models.py`:
   ```bash
   # Create these files:
   app/models/spot.py
   app/models/review.py
   app/models/image.py
   app/models/location.py
   app/models/dive_shop.py
   app/models/tag.py
   ```

2. **Move model-specific logic** from the main models file to individual files.

### Step 2: Create Service Classes

1. **Extract business logic** from route files into service classes:
   ```python
   # Example: app/services/spot_service.py
   class SpotService:
       @staticmethod
       def get_spots_by_location(latitude, longitude, radius=50):
           # Business logic here
           pass

       @staticmethod
       def create_spot(spot_data, user_id):
           # Business logic here
           pass
   ```

2. **Move helper functions** from `app/helpers/` into appropriate service classes.

### Step 3: Refactor Route Files

1. **Simplify route handlers** to only handle HTTP concerns:
   ```python
   # Before (in routes):
   @bp.route('/spots', methods=['GET'])
   def get_spots():
       # Complex business logic here
       pass

   # After (in routes):
   @bp.route('/spots', methods=['GET'])
   def get_spots():
       result = SpotService.get_spots_by_location(
           latitude=request.args.get('lat'),
           longitude=request.args.get('lng')
       )
       return jsonify(result)
   ```

2. **Create new API blueprints** for each domain:
   - `app/api/spots.py`
   - `app/api/reviews.py`
   - `app/api/locations.py`
   - etc.

### Step 4: Update Imports

1. **Update all import statements** throughout the codebase:
   ```python
   # Old imports
   from app.models import User, Spot, Review
   from app.helpers.create_account import create_account

   # New imports
   from app.models.user import User
   from app.models.spot import Spot
   from app.models.review import Review
   from app.services.auth_service import AuthService
   ```

### Step 5: Create Schemas (Optional)

1. **Add request/response schemas** for better API documentation:
   ```python
   # app/schemas/user_schemas.py
   from marshmallow import Schema, fields

   class UserSchema(Schema):
       id = fields.Int(dump_only=True)
       email = fields.Email(required=True)
       first_name = fields.Str(required=True)
       last_name = fields.Str(required=True)
   ```

## Benefits of New Structure

### 1. **Separation of Concerns**
- Models: Data structure and database operations
- Services: Business logic and data processing
- API: HTTP handling and request/response formatting
- Utils: Reusable utility functions

### 2. **Testability**
- Services can be unit tested independently
- API endpoints can be tested with mocked services
- Models can be tested with database fixtures

### 3. **Maintainability**
- Related functionality is grouped together
- Changes to business logic don't affect API layer
- Clear dependencies between layers

### 4. **Scalability**
- Easy to add new services without affecting existing code
- Clear boundaries for team collaboration
- Modular structure supports microservices migration

### 5. **Code Reusability**
- Services can be used by multiple API endpoints
- Utils can be shared across the application
- Models provide consistent data access patterns

## Implementation Priority

1. **High Priority**:
   - Complete model separation
   - Create core services (auth, user, spot)
   - Refactor main route files

2. **Medium Priority**:
   - Create remaining services
   - Add comprehensive validation
   - Implement error handling middleware

3. **Low Priority**:
   - Add schemas for API documentation
   - Create custom decorators
   - Add comprehensive logging

## Testing Strategy

1. **Unit Tests**: Test services and utils independently
2. **Integration Tests**: Test API endpoints with mocked services
3. **End-to-End Tests**: Test complete user workflows

## Example Migration

Here's an example of how to migrate a route:

**Before** (`app/routes/spots.py`):
```python
@bp.route('/spots', methods=['GET'])
def get_spots():
    latitude = request.args.get('lat')
    longitude = request.args.get('lng')
    radius = request.args.get('radius', 50)

    # Complex business logic here
    spots = Spot.query.filter(
        Spot.latitude.between(latitude - radius, latitude + radius),
        Spot.longitude.between(longitude - radius, longitude + radius)
    ).all()

    # More business logic...
    return jsonify([spot.get_dict() for spot in spots])
```

**After**:
```python
# app/services/spot_service.py
class SpotService:
    @staticmethod
    def get_spots_by_location(latitude, longitude, radius=50):
        spots = Spot.query.filter(
            Spot.latitude.between(latitude - radius, latitude + radius),
            Spot.longitude.between(longitude - radius, longitude + radius)
        ).all()
        return [spot.get_dict() for spot in spots]

# app/api/spots.py
@bp.route('/spots', methods=['GET'])
def get_spots():
    result = SpotService.get_spots_by_location(
        latitude=request.args.get('lat'),
        longitude=request.args.get('lng'),
        radius=request.args.get('radius', 50)
    )
    return jsonify(result)
```

This restructuring will make your codebase more maintainable, testable, and scalable while following Flask best practices and MVC principles.