from app.models.dive_shop import DiveShop
from app.models.image import Image
from app.models.location import AreaOne, AreaTwo, Country, Locality
from app.models.review import Review
from app.models.spot import ShoreDivingData, ShoreDivingReview, Spot, WannaDiveData
from app.models.tag import Tag, tags
from app.models.user import DivePartnerAd, PasswordReset, User

__all__ = [
    'User', 'PasswordReset', 'DivePartnerAd',
    'Spot', 'ShoreDivingData', 'ShoreDivingReview', 'WannaDiveData',
    'Review', 'Image',
    'Country', 'AreaOne', 'AreaTwo', 'Locality',
    'DiveShop', 'Tag', 'tags'
]