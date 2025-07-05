# Geographic Migration Testing Guide

This guide will help you safely test the geographic hierarchy migration with full rollback capabilities.

## 🚨 **Important Safety Notes**

- **Always test on a copy of your production database**
- **Keep your production database backed up**
- **Test in a staging environment first**
- **The migration has rollback capabilities built-in**

## 📋 **Pre-Testing Checklist**

### 1. Database Backup
```bash
# Create a backup of your current database
cp your_database.db your_database_backup_$(date +%Y%m%d_%H%M%S).db
```

### 2. Environment Setup
```bash
# Make sure you're in your development environment
export FLASK_ENV=development
export FLASK_DEBUG=1
```

### 3. Check Current Database State
```bash
# Check current migration status
flask db current
flask db history
```

## 🧪 **Step-by-Step Testing Process**

### **Phase 1: Database Migration Testing**

#### Step 1: Run the Migration
```bash
# Apply the migration
flask db upgrade

# Verify the migration was applied
flask db current
```

#### Step 2: Verify Database Changes
```bash
# Check that new tables and columns were created
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    # Check if geographic_node table exists
    result = db.session.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"geographic_node\"')
    print('Geographic node table exists:', result.fetchone() is not None)

    # Check if new columns were added
    result = db.session.execute('PRAGMA table_info(spot)')
    columns = [row[1] for row in result.fetchall()]
    print('geographic_node_id column exists:', 'geographic_node_id' in columns)
"
```

#### Step 3: Test Rollback (Optional)
```bash
# Test that you can rollback the migration
flask db downgrade

# Verify rollback worked
flask db current

# Re-apply the migration
flask db upgrade
```

### **Phase 2: Data Migration Testing**

#### Step 1: Create Geographic Nodes
```bash
# Run the geographic hierarchy migration
python scripts/migrate_geographic_hierarchy.py
```

#### Step 2: Verify Node Creation
```bash
python -c "
from app import create_app, db
from app.models import GeographicNode, Country, AreaOne, AreaTwo, Locality

app = create_app()
with app.app_context():
    # Check node counts
    total_nodes = GeographicNode.query.count()
    countries = Country.query.count()
    area_ones = AreaOne.query.count()
    area_twos = AreaTwo.query.count()
    localities = Locality.query.count()

    print(f'Total geographic nodes: {total_nodes}')
    print(f'Countries: {countries}')
    print(f'Area Ones: {area_ones}')
    print(f'Area Twos: {area_twos}')
    print(f'Localities: {localities}')

    # Show some sample nodes
    sample_nodes = GeographicNode.query.limit(5).all()
    for node in sample_nodes:
        print(f'- {node.name} (level {node.admin_level})')
"
```

#### Step 3: Test URL Generation
```bash
python -c "
from app import create_app
from app.models import GeographicNode

app = create_app()
with app.app_context():
    nodes = GeographicNode.query.limit(3).all()
    for node in nodes:
        print(f'{node.name}: {node.get_url()}')
"
```

### **Phase 3: Spot Migration Testing**

#### Step 1: Migrate Sample Spots
```bash
# Run spot migration (this will migrate all spots)
python scripts/migrate_spots_to_geographic_nodes.py
```

#### Step 2: Verify Spot Migration
```bash
python -c "
from app import create_app, db
from app.models import Spot

app = create_app()
with app.app_context():
    total_spots = Spot.query.count()
    spots_with_nodes = Spot.query.filter(Spot.geographic_node_id.isnot(None)).count()

    print(f'Total spots: {total_spots}')
    print(f'Spots with geographic nodes: {spots_with_nodes}')
    print(f'Migration percentage: {(spots_with_nodes / total_spots * 100):.1f}%')

    # Test URL generation for some spots
    sample_spots = Spot.query.filter(Spot.geographic_node_id.isnot(None)).limit(3).all()
    for spot in sample_spots:
        print(f'{spot.name}: {spot.get_url()}')
"
```

### **Phase 4: API Testing**

#### Step 1: Start Your Flask Server
```bash
# Start the development server
flask run
```

#### Step 2: Run Comprehensive Tests
```bash
# Run the automated testing script
python scripts/test_geographic_migration.py --base-url http://localhost:5000
```

#### Step 3: Manual URL Testing
Test these URLs in your browser or with curl:

**New Geographic URLs:**
```bash
curl http://localhost:5000/loc/us
curl http://localhost:5000/loc/us/ca
curl http://localhost:5000/loc/us/ca/san-diego
```

**Legacy URLs (should redirect):**
```bash
curl -I http://localhost:5000/loc/us/_/ca/san-diego
curl -I http://localhost:5000/Beach/1/test-spot
```

**Spot URLs:**
```bash
# Test a specific spot (replace with actual spot ID)
curl http://localhost:5000/loc/us/ca/san-diego/la-jolla-cove
```

### **Phase 5: Data Integrity Testing**

#### Step 1: Verify Legacy Data Access
```bash
python -c "
from app import create_app
from app.models import Spot

app = create_app()
with app.app_context():
    # Test that spots can still access legacy data
    spots = Spot.query.limit(5).all()
    for spot in spots:
        print(f'Spot: {spot.name}')
        print(f'  Country: {spot.country.name if spot.country else \"None\"}')
        print(f'  Area One: {spot.area_one.name if spot.area_one else \"None\"}')
        print(f'  Geographic Node: {spot.geographic_node.name if spot.geographic_node else \"None\"}')
        print()
"
```

#### Step 2: Test URL Consistency
```bash
python -c "
from app import create_app
from app.models import Spot

app = create_app()
with app.app_context():
    # Test that both old and new URL methods work
    spots = Spot.query.limit(3).all()
    for spot in spots:
        print(f'Spot: {spot.name}')
        print(f'  Legacy URL: {spot.get_legacy_url()}')
        print(f'  New URL: {spot.get_url()}')
        print()
"
```

## 🔄 **Rollback Procedures**

### **If You Need to Rollback the Migration**

#### Option 1: Database Rollback
```bash
# Rollback the migration
flask db downgrade

# Verify rollback
flask db current
```

#### Option 2: Manual Cleanup (if needed)
```bash
python -c "
from app import create_app, db
from app.models import GeographicNode

app = create_app()
with app.app_context():
    # Remove all geographic nodes
    GeographicNode.query.delete()
    db.session.commit()
    print('All geographic nodes removed')
"
```

#### Option 3: Restore from Backup
```bash
# Stop the Flask server
# Restore your backup
cp your_database_backup_YYYYMMDD_HHMMSS.db your_database.db
# Restart the Flask server
```

## 📊 **Testing Checklist**

- [ ] Database migration runs successfully
- [ ] Migration can be rolled back
- [ ] Geographic nodes are created from existing data
- [ ] URLs are generated correctly
- [ ] Legacy URLs redirect properly
- [ ] New URLs work correctly
- [ ] Spots can be migrated to use geographic nodes
- [ ] Data integrity is maintained
- [ ] Legacy data access still works
- [ ] Performance is acceptable

## 🚀 **Production Deployment**

Once testing is complete:

1. **Backup production database**
2. **Deploy code changes**
3. **Run migration in production**
4. **Run data migration scripts**
5. **Monitor for any issues**
6. **Update frontend to use new URLs gradually**

## 📈 **Monitoring After Deployment**

Monitor these metrics:
- 301 redirect response times
- 404 error rates
- New URL usage vs old URL usage
- Database performance
- User experience metrics

## 🆘 **Troubleshooting**

### Common Issues:

1. **Migration fails**: Check database permissions and disk space
2. **URLs not working**: Verify Flask routes are registered correctly
3. **Redirects not working**: Check that legacy_redirects blueprint is registered
4. **Performance issues**: Monitor database query performance
5. **Data inconsistencies**: Run data integrity checks

### Getting Help:
- Check the test results file: `geographic_migration_test_results.json`
- Review Flask application logs
- Check database migration history: `flask db history`