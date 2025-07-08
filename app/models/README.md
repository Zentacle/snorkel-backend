# Models Package

This package contains all database models for the Snorkel Backend application, organized by domain for better maintainability.

## Structure

```
app/models/
├── __init__.py          # Main package init - imports all models
├── base.py              # Database setup and common utilities
├── geographic.py        # Geographic hierarchy models
├── user.py              # User-related models
├── dive.py              # Dive-related models
├── shop.py              # Shop-related models
├── external.py          # External data models
├── system.py            # System models
└── README.md            # This file
```

## Model Categories

### Base (`base.py`)
- `tags`: Association table for many-to-many relationship between spots and tags

### Geographic (`geographic.py`)
- `GeographicNode`: Flexible geographic hierarchy node
- `Country`: Country-level geographic entities
- `AreaOne`: State/province level geographic entities
- `AreaTwo`: County level geographic entities
- `Locality`: City/town level geographic entities

### User (`user.py`)
- `User`: User account information
- `PasswordReset`: Password reset tokens

### Dive (`dive.py`)
- `Spot`: Dive spot/location information
- `Review`: User reviews of dive spots
- `Image`: Images associated with spots and reviews
- `Tag`: Tags for categorizing spots

### Shop (`shop.py`)
- `DiveShop`: Dive shop information and services
- `DivePartnerAd`: Dive partner advertisements

### External (`external.py`)
- `ShoreDivingData`: Data imported from ShoreDiving.com
- `ShoreDivingReview`: Review data from ShoreDiving.com
- `WannaDiveData`: Data imported from WannaDive.com

### System (`system.py`)
- `ScheduledEmail`: Email scheduling for automated communications

## Usage

All models can be imported from the main package:

```python
from app.models import db, User, Spot, Review, DiveShop
```

Or import specific models from their modules:

```python
from app.models.user import User
from app.models.dive import Spot, Review
```

## Benefits of This Structure

1. **Better Organization**: Models are grouped by domain/functionality
2. **Easier Maintenance**: Related models are in the same file
3. **Clearer Dependencies**: Each module shows its dependencies clearly
4. **Reduced File Size**: No more 1100+ line monolithic file
5. **Better IDE Support**: Easier to navigate and find specific models
6. **Team Collaboration**: Multiple developers can work on different model categories simultaneously

## Migration Notes

- All existing imports using `from app.models import ...` continue to work
- The database instance `db` is still available from `app.models`
- All relationships and foreign keys remain unchanged
- No database migrations are required for this reorganization
