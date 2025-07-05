# Geographic Hierarchy Migration

This document explains the new flexible geographic hierarchy system that replaces the rigid 4-level hierarchy (Country → AreaOne → AreaTwo → Locality) with a more flexible tree-based structure.

## Overview

### Old System Problems
- Rigid 4-level hierarchy that doesn't work for all countries
- Confusing URLs with `_` placeholders (e.g., `/loc/us/_/ca/san-diego`)
- Complex query logic with multiple nullable fields
- Separate URL patterns for locations (`/loc/`) and spots (`/Beach/`)

### New System Benefits
- **Flexible URLs**: Clean URLs like `/loc/us/ca/san-diego` or `/loc/fr/paris`
- **Better SEO**: Hierarchical URLs that search engines understand
- **Simplified Queries**: Single `geographic_node_id` field instead of multiple nullable fields
- **Unified URL Structure**: Both locations and spots use `/loc/` prefix
- **Backwards Compatibility**: 301 redirects ensure old URLs continue to work

## New URL Structure

### Geographic Locations
- **Country**: `/loc/us`
- **State/Province**: `/loc/us/ca`
- **County**: `/loc/us/ca/san-diego-county`
- **City**: `/loc/us/ca/san-diego`

### Spots (Dive Locations)
- **With Geographic Context**: `/loc/us/ca/san-diego/la-jolla-cove`
- **Legacy Fallback**: `/Beach/123/la-jolla-cove` (redirects to new format)

## Implementation

### 1. New Models

#### GeographicNode
```python
class GeographicNode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    short_name = db.Column(db.String, nullable=False, unique=True)

    # Hierarchy relationships
    parent_id = db.Column(db.Integer, db.ForeignKey('geographic_node.id'))
    root_id = db.Column(db.Integer, db.ForeignKey('geographic_node.id'))

    # Geographic metadata
    admin_level = db.Column(db.Integer)  # 0=country, 1=state, 2=county, 3=city
    country_code = db.Column(db.String(2))

    # Legacy mapping fields
    legacy_country_id = db.Column(db.Integer, db.ForeignKey('country.id'))
    legacy_area_one_id = db.Column(db.Integer, db.ForeignKey('area_one.id'))
    legacy_area_two_id = db.Column(db.Integer, db.ForeignKey('area_two.id'))
    legacy_locality_id = db.Column(db.Integer, db.ForeignKey('locality.id'))
```

#### Updated Spot Model
```python
class Spot(db.Model):
    # ... existing fields ...
    geographic_node_id = db.Column(db.Integer, db.ForeignKey('geographic_node.id'))

    def get_url(self):
        """Get new geographic-based URL or fall back to legacy"""
        if self.geographic_node:
            path = self.geographic_node.get_path_to_root()
            path.append(self)
            return '/loc/' + '/'.join([node.short_name for node in path])
        else:
            return self.get_legacy_url()
```

### 2. URL Mapping Service

The `URLMappingService` handles the transition between old and new systems:

```python
class URLMappingService:
    @staticmethod
    def find_node_by_legacy_path(country, area_one=None, area_two=None, locality=None):
        """Find geographic node by legacy path components"""

    @staticmethod
    def create_legacy_mapping(country, area_one=None, area_two=None, locality=None):
        """Create mapping between legacy entities and new geographic node"""
```

### 3. New Routing System

#### Geographic Routes (`/loc/`)
- **Flexible Path Matching**: `/loc/<path:geographic_path>`
- **Spot Detection**: Automatically detects if the last path segment is a spot name
- **Legacy Redirects**: Handles old URL patterns with 301 redirects

#### Legacy Redirects
- **Old Location URLs**: `/loc/country/area_one/area_two/locality` → new format
- **Old Spot URLs**: `/Beach/id/name` → new geographic format

### 4. Migration Process

#### Phase 1: Database Migration
```bash
# Run the database migration
flask db upgrade
```

#### Phase 2: Populate Geographic Nodes
```bash
# Create geographic nodes from existing hierarchy
python scripts/migrate_geographic_hierarchy.py
```

#### Phase 3: Migrate Spots
```bash
# Assign geographic nodes to existing spots
python scripts/migrate_spots_to_geographic_nodes.py
```

#### Phase 4: Verify Migration
```bash
# Check migration status
python scripts/migrate_spots_to_geographic_nodes.py
```

## URL Examples

### Before (Old System)
- Location: `/loc/us/_/ca/san-diego`
- Spot: `/Beach/123/la-jolla-cove`

### After (New System)
- Location: `/loc/us/ca/san-diego`
- Spot: `/loc/us/ca/san-diego/la-jolla-cove`

### Redirects (Backwards Compatibility)
- `/loc/us/_/ca/san-diego` → `/loc/us/ca/san-diego` (301)
- `/Beach/123/la-jolla-cove` → `/loc/us/ca/san-diego/la-jolla-cove` (301)

## Benefits

### SEO Improvements
- **Clean URLs**: No more confusing `_` placeholders
- **Hierarchical Structure**: URLs reflect geographic hierarchy
- **Keyword-Rich**: Location names in URLs improve search rankings
- **Consistent Pattern**: All URLs follow the same structure

### User Experience
- **Intuitive URLs**: Users can understand the location from the URL
- **Bookmarkable**: Clean URLs are easier to bookmark and share
- **Predictable**: Users can guess URLs based on location names

### Technical Benefits
- **Simplified Queries**: Single field instead of multiple nullable fields
- **Flexible Hierarchy**: Works for any country structure
- **Scalable**: Easy to add new geographic levels
- **Maintainable**: Centralized geographic logic

## Migration Strategy

### Gradual Rollout
1. **Deploy New System**: Add new models and routes alongside existing system
2. **Migrate Data**: Run migration scripts to populate geographic nodes
3. **Update Frontend**: Gradually update frontend to use new URLs
4. **Monitor Redirects**: Track 301 redirect usage to ensure compatibility
5. **Deprecate Legacy**: After sufficient time, deprecate legacy fields

### Rollback Plan
- Keep legacy fields and routes during transition
- Monitor error rates and redirect performance
- Can easily revert to old system if issues arise

## Monitoring

### Key Metrics
- **Redirect Performance**: Monitor 301 redirect response times
- **Error Rates**: Track 404 errors on old URLs
- **Migration Progress**: Monitor percentage of spots with geographic nodes
- **URL Usage**: Track usage of new vs old URL patterns

### Health Checks
- Verify all old URLs redirect properly
- Ensure new URLs return correct data
- Monitor database performance with new queries

## Future Enhancements

### Potential Improvements
- **Geographic Search**: Enhanced search by geographic proximity
- **Regional Content**: Location-specific content and recommendations
- **Multi-language Support**: URLs in local languages
- **Geographic Analytics**: Track user behavior by region

### API Enhancements
- **Geographic API**: Endpoints for geographic hierarchy queries
- **Proximity Search**: Find spots near a location
- **Regional Statistics**: Geographic distribution of spots and reviews