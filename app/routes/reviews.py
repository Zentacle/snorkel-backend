import datetime
import os

from flask import Blueprint, abort, render_template, request
from flask_jwt_extended import get_current_user, jwt_required
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from app import cache, db
from app.models import Review, ShoreDivingReview, Spot

bp = Blueprint("reviews", __name__, url_prefix="/reviews")


@bp.route("/recent")
def get_recent_reviews():
    """Get Recent Reviews
    ---
    get:
        summary: Get recent reviews
        description: Get recent reviews
        responses:
            200:
                description: Returns review object
                content:
                  application/json:
                    schema: ReviewSchema
    """
    limit = request.args.get("limit") if request.args.get("limit") else 25
    offset = request.args.get("offset") if request.args.get("offset") else 0
    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")
    reviews = Review.query.options(joinedload("spot")).options(joinedload("user"))
    if request.args.get("type") == "nearby" and latitude:
        nearby_spots = (
            db.session.query(Spot.id)
            .filter(Spot.distance(latitude, longitude) < 50)
            .filter(Spot.is_deleted.is_not(True))
            .subquery()
        )
        reviews = reviews.filter(
            and_(
                Review.beach_id.in_(nearby_spots),
                Review.is_private.is_not(True),
                Review.beach_id != 19,
            )
        )

    reviews = (
        reviews.filter(Review.beach_id != 19).order_by(Review.date_posted.desc()).limit(limit).offset(offset).all()
    )
    data = []
    for review in reviews:
        review_data = review.get_dict()
        review_data["spot"] = review.spot.get_dict()
        review_data["user"] = review.user.get_dict()
        data.append(review_data)
    return {"data": data}


@bp.route("/get")
@cache.cached(query_string=True)
def get_reviews():
    """Get Reviews
    ---
    get:
        summary: Get Reviews for spot
        description: Get Reviews for spot
        parameters:
            - name: beach_id
              in: body
              description: beach_id
              type: integer
              required: true
            - name: limit
              in: body
              description: limit on number of reviews to fetch
              type: integer
              required: false
            - name: offset
              in: body
              description: offset to start if paginating through reviews
              type: integer
              required: false
        responses:
            200:
                description: Returns review object
                content:
                  application/json:
                    schema: ReviewSchema
    """
    sd_id = request.args.get("sd_review_id")
    if sd_id:
        review = Review.query.filter(Review.shorediving_data.has(shorediving_id=sd_id)).first()
        if review:
            data = review.get_dict()
            data["user"] = review.user.get_dict()
            return {"data": [data]}
    beach_id = request.args.get("beach_id")
    limit = request.args.get("limit")
    offset = int(request.args.get("offset")) if request.args.get("offset") else 0

    query = (
        Review.query.options(joinedload("user"))
        .options(joinedload("shorediving_data"))
        .options(joinedload("images"))
        .order_by(Review.date_posted.desc())
        .filter_by(beach_id=beach_id)
    )
    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    reviews = query.all()
    output = []
    for review in reviews:
        data = review.get_dict()
        data["user"] = review.user.get_dict()
        try:
            data["shorediving_data"] = review.shorediving_data.get_dict()
        except Exception:
            pass
        image_data = []
        signedUrls = []
        for image in review.images:
            image_data.append(image.get_dict())
            signedUrls.append(image.url)
        data["images"] = image_data
        data["signedUrls"] = signedUrls
        output.append(data)
    return {"data": output, "next_offset": offset + len(output)}


@bp.route("/delete", methods=["POST"])
@jwt_required()
def delete_shore_diving_ids():
    user = get_current_user()
    if not user.admin:
        abort(403, "You must be an admin to that")
    id = request.json.get("id")
    sd_review = ShoreDivingReview.query.filter_by(shorediving_id=id).first_or_404()
    review = sd_review.review
    db.session.delete(sd_review)
    db.session.delete(review)
    db.session.commit()
    return "ok"


@bp.route("/recentemail")
def send_recent_reviews():
    date = datetime.datetime.now() - datetime.timedelta(days=7)
    date_str = datetime.date.strftime(date, "%m-%d-%Y") if not request.args.get("date") else request.args.get("date")
    reviews = (
        Review.query.options(joinedload("user"))
        .options(joinedload("spot"))
        .filter(Review.text.is_not(None))
        .filter(Review.date_posted > date_str)
        .order_by(func.length(Review.text).desc())
        .limit(10)
        .all()
    )
    first_name = "Mayank"
    html = render_template(
        "recent_reviews_email.html",
        first_name=first_name,
        reviews=reviews,
    )
    message = Mail(
        from_email=("hello@zentacle.com", "Zentacle"),
        to_emails="mayank@zentacle.com",
        subject="Recent activity on dive sites near you",
        html_content=html,
    )
    message.reply_to = "mayank@zentacle.com"
    SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
    print(html)
    return {"data": html.replace("\n", "")}
    # response = sg.send(message)
    return "ok"
