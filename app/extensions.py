from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask extensions
db = SQLAlchemy()
cors = CORS()
cache = Cache()
jwt_manager = JWTManager()
migrate = Migrate(compare_type=True)