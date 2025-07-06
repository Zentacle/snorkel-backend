from app import db
from app.models import AreaOne, AreaTwo, Locality, Spot


def merge_area_one(stable_id, remove_id):
    results = []
    area_twos = AreaTwo.query.filter_by(area_one_id=remove_id).all()
    for area_two in area_twos:
        results.append(area_two.get_dict())
        area_two.area_one_id = stable_id

    localities = Locality.query.filter_by(area_one_id=remove_id).all()
    for locality in localities:
        results.append(locality.get_dict())
        locality.area_one_id = stable_id

    spots = Spot.query.filter_by(area_one_id=remove_id).all()
    for spot in spots:
        results.append(spot.get_dict())
        spot.area_one_id = stable_id

    AreaOne.query.filter_by(id=remove_id).delete()
    db.session.commit()
    return results
