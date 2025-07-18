import io
import json
import os

import bcrypt
import boto3
import jwt
import requests
from flask import Blueprint, abort, request
from flask.helpers import make_response
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.helpers.create_account import create_account
from app.helpers.get_localities import format_localities
from app.helpers.login import login
from app.helpers.phone_validation import format_phone_to_e164, validate_phone_format
from app.helpers.send_notifications import send_notification
from app.models import Review, User

bp = Blueprint("user", __name__, url_prefix="/user")

"""
Auth data goes in a cookie
"""


@bp.route("/register", methods=["POST"])
def user_signup():
    """Register
    ---
    post:
        summary: Register new user endpoint.
        description: Register a new user
        parameters:
            - name: first_name
              in: body
              description: First Name
              type: string
              required: true
            - name: last_name
              in: body
              description: Last Name
              type: string
              required: true
            - name: email
              in: body
              description: Email address
              type: string
              required: true
            - name: username
              in: body
              description: Username
              type: string
              required: false
            - name: profile_pic
              in: body
              description: Profile Pic
              type: string
              required: false
            - name: password
              in: body
              description: Password
              type: string
              required: false
            - name: phone
              in: body
              description: Phone number (will be stored in E.164 format)
              type: string
              required: false
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      msg: string
                description: User couldn't be created.
    """
    first_name = request.json.get("first_name") or ""
    last_name = request.json.get("last_name") or ""
    email = request.json.get("email")
    username = request.json.get("username")
    profile_pic = request.json.get("profile_pic")
    unencrypted_password = request.json.get("password")
    phone = request.json.get("phone")
    app_name = request.json.get("app")
    display_name = first_name + " " + last_name

    resp = create_account(
        db,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        email=email,
        profile_pic=profile_pic,
        username=username,
        unencrypted_password=unencrypted_password,
        app_name=app_name,
        phone=phone,
    )
    return resp


@bp.route("/apple_register", methods=["POST"])
def user_apple_signup():
    """Apple Register
    ---
    post:
        summary: Register new user with Apple auth endpoint.
        description: Register a new user with Apple auth
        requestBody:
          content:
            application/json:
              schema: AppleRegisterSchema
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      msg: string
                description: User couldn't be created.
    """
    # https://developer.apple.com/documentation/sign_in_with_apple/sign_in_with_apple_js/configuring_your_webpage_for_sign_in_with_apple
    request.json.get("code")
    id_token = request.json.get("id_token")
    request.json.get("state")
    audience = (
        request.json.get("audience")
        if request.json.get("audience")
        else os.environ.get("APPLE_APP_ID")
    )
    app_name = request.json.get("app")
    email = None

    # https://gist.github.com/davidhariri/b053787aabc9a8a9cc0893244e1549fe
    key_payload = requests.get("https://appleid.apple.com/auth/keys").json()
    token_headers = jwt.get_unverified_header(id_token)
    jwk = None
    for key in key_payload["keys"]:
        if key.get("kid") == token_headers.get("kid"):
            jwk = key
    if not jwk:
        abort(500, "No matching key found")
    public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))

    try:
        token = jwt.decode(
            id_token, public_key, audience=audience, algorithms=["RS256"]
        )
    except jwt.exceptions.ExpiredSignatureError:
        raise Exception("That token has expired")
    except jwt.exceptions.InvalidAudienceError:
        raise Exception("That token's audience did not match")
    except Exception as e:
        print(e)
        raise Exception("An unexpected error occoured")
    if not email:
        email = token.get("email")

    user = User.query.filter(func.lower(User.email) == email.lower()).first()
    if user:
        return login(user)

    # renamed  to avoid confusion and possible name clashes
    user_body = request.json.get("user")
    if user_body:
        email = user_body.get("email") if user_body.get("email") else email
        first_name = (
            user_body.get("name").get("firstName")
            if user_body.get("name").get("firstName")
            else email
        )
        last_name = (
            user_body.get("name").get("lastName")
            if user_body.get("name").get("lastName")
            else ""
        )
        display_name = first_name + " " + last_name

        return create_account(
            db,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            email=email,
            app_name=app_name,
        )

    abort(422, "user doesn't exist and didn't get a user object")


@bp.route("/google_register", methods=["POST"])
def user_google_signup():
    """Google Register
    ---
    post:
        summary: Register new user with Google auth endpoint.
        description: Register a new user with Google auth
        parameters:
            - name: credential
              in: body
              description: google oauth token credential returned from Google login button
              type: string
              required: true
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      msg: string
                description: User couldn't be created.
    """
    token = request.json.get("credential")
    app_name = request.json.get("app")
    userid = None
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), os.environ.get("GOOGLE_CLIENT_ID")
        )

        # Or, if multiple clients access the backend server:
        # idinfo = id_token.verify_oauth2_token(token, requests.Request())
        # if idinfo['aud'] not in [CLIENT_ID_1, CLIENT_ID_2, CLIENT_ID_3]:
        #     raise ValueError('Could not verify audience.')

        # If auth request is from a G Suite domain:
        # if idinfo['hd'] != GSUITE_DOMAIN_NAME:
        #     raise ValueError('Wrong hosted domain.')

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        email = idinfo.get("email")
        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if user:
            return login(user)
        first_name = idinfo.get("given_name")
        last_name = idinfo.get("family_name")
        display_name = idinfo.get("name")
        profile_pic = idinfo.get("picture")
        resp = create_account(
            db,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            email=email,
            profile_pic=profile_pic,
            app_name=app_name,
        )
        return resp
    except ValueError as e:
        abort(401, e.body)
        # Invalid token
    return {"data": userid, "token": token}


@bp.route("/register/password", methods=["POST"])
def user_finish_signup():
    """Add account password
    ---
    post:
        summary: Add password for a newly registered user. Can't be used to change password.
        description: Add password for a newly registered user. Can't be used to change password.
        parameters:
            - name: user_id
              in: body
              description: User ID (not username)
              type: string
              required: true
            - name: password
              in: body
              description: password
              type: string
              required: true
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: User couldn't be created.
    """
    user_id = request.json.get("user_id")
    user = User.query.filter_by(id=user_id).first()
    if user.password:
        abort(401, "This user has already registered a password")
    unencrypted_password = request.json.get("password")
    password = bcrypt.hashpw(
        unencrypted_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    user.password = password
    db.session.commit()
    auth_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    responseObject = {
        "status": "success",
        "message": "Successfully registered.",
        "auth_token": auth_token,
        "username": user.username,
    }
    resp = make_response(responseObject)
    set_access_cookies(resp, auth_token)
    set_refresh_cookies(resp, refresh_token)
    return resp


"""
Save the response token as an Authorization header with the format
Authorization: Bearer <token>
"""


@bp.route("/login", methods=["POST"])
def user_login():
    """Login
    ---
    post:
        summary: login with username/email and password
        description: login with username/email and password
        parameters:
            - name: email
              in: body
              description: username or password
              type: string
              required: true
            - name: password
              in: body
              description: password
              type: string
              required: true
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Wrong password.
    """
    email = request.json.get("email")
    password = request.json.get("password")

    user = User.query.filter(
        or_(func.lower(User.email) == email.lower(), User.username == email)
    ).first()
    if not user:
        abort(400, "Wrong password or user does not exist")
    if bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        return login(user)
    else:
        abort(400, "Wrong password or user does not exist")


@bp.route("/logout")
def logout():
    resp = make_response({"msg": "Successfully logged out"})
    unset_jwt_cookies(resp)
    return resp


@bp.route("/patch", methods=["PATCH"])
@jwt_required()
def patch_user():
    """Patch User
    ---
    patch:
        summary: Update user profile
        description: Update user profile fields. Include the fields you want to change in the request body. Phone numbers will be automatically formatted to E.164 format.
        parameters:
          - name: id
            in: body
            description: user id (admin only)
            type: int
            required: false
          - name: email
            in: body
            description: user email (admin only)
            type: string
            required: false
          - name: username
            in: body
            description: username (must be alphanumeric)
            type: string
            required: false
          - name: phone
            in: body
            description: phone number (will be stored in E.164 format)
            type: string
            required: false
          - name: first_name
            in: body
            description: first name
            type: string
            required: false
          - name: last_name
            in: body
            description: last name
            type: string
            required: false
          - name: bio
            in: body
            description: user bio
            type: string
            required: false
          - name: hometown
            in: body
            description: hometown
            type: string
            required: false
          - name: unit
            in: body
            description: preferred unit system (imperial/metric)
            type: string
            required: false
          - name: latitude
            in: body
            description: latitude (will also update hometown)
            type: float
            required: false
          - name: longitude
            in: body
            description: longitude (will also update hometown)
            type: float
            required: false
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
    """
    user = get_current_user()
    user_id = request.json.get("id")
    email = request.json.get("email")
    updates = request.json
    if user.admin and user_id:
        user = User.query.filter_by(id=user_id).first_or_404()
    elif user.admin and email:
        user = User.query.filter_by(email=email).first_or_404()
        updates.pop("email", None)

    updates.pop("id", None)
    for key in updates.keys():
        if key == "username":
            username = updates.get(key).lower()
            same_username_user = User.query.filter_by(username=username).first()
            if not username.isalnum():
                abort(422, "Usernames can't have special characters")
            if same_username_user and user.id != same_username_user.id:
                abort(401, "Someone already has that username")
            setattr(user, key, username.lower())
        elif key == "phone":
            phone = updates.get(key)
            if phone:
                if not validate_phone_format(phone):
                    abort(422, "Please enter a valid phone number")
                formatted_phone = format_phone_to_e164(phone)
                setattr(user, key, formatted_phone)
            else:
                setattr(user, key, None)
        elif key == "latitude":
            setattr(user, key, updates.get(key))
            latitude = updates.get("latitude")
            longitude = updates.get("longitude")
            r = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "latlng": f"{latitude},{longitude}",
                    "key": os.environ.get("GOOGLE_API_KEY"),
                },
            )
            response = r.json()
            if response.get("status") == "OK":
                address_components = response.get("results")[0].get(
                    "address_components"
                )
                components = format_localities(address_components)
                if components.get("locality") and components.get("area_1"):
                    city_name = components.get("locality").get("long_name")
                    state_name = components.get("area_1").get("short_name")
                    hometown = f"{city_name}, {state_name}"
                    setattr(user, "hometown", hometown)
                elif components.get("area_1") and components.get("country"):
                    city_name = components.get("area_1").get("long_name")
                    country_name = components.get("country").get("short_name")
                    hometown = f"{city_name}, {country_name}"
                    setattr(user, "hometown", hometown)
        else:
            setattr(user, key, updates.get(key))
    db.session.commit()
    user.id
    return user.get_dict(), 200


@bp.route("/me")
@jwt_required(refresh=True)
def get_me():
    """Fetch Current User
    ---
    get:
        summary: fetch current user (without reviews)
        description: fetch current user. Store auth token in header as Authorization: `Bearer ${token}`
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
    """
    user = get_current_user()
    auth_token = create_access_token(identity=user.id)
    resp_data = user.get_dict()

    resp_data["email"] = user.email
    resp_data["access_token"] = auth_token
    resp = make_response(resp_data)
    set_access_cookies(resp, auth_token)
    return resp


@bp.route("/get")
@jwt_required(optional=True)
def get_user():
    """Get User
    ---
    get:
        summary: Get User
        description: Get User (and their reviews)
        parameters:
            - name: username
              in: body
              description: username
              type: string
              required: true
        responses:
            200:
                description: Returns user object
                content:
                  application/json:
                    schema: UserSchema
    """
    username = request.args.get("username")
    user_id = request.args.get("user_id")
    if username == "null" or username == "undefined":
        username = None
    user = get_current_user()
    if not username and not user_id:
        if not user:
            abort(
                422,
                "Include a username or user id in the request. If you are trying to get the logged in user, use /user/me",
            )
    if username:
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
    if not user and user_id:
        user = User.query.filter(User.id == user_id).first()
    if not user:
        abort(404, f"User username={username}, user_id={user_id} doesn't exist")

    reviews = (
        Review.query.filter_by(author_id=user.id)
        .options(joinedload("images"))
        .order_by(Review.date_dived.desc())
        .all()
    )
    user_data = user.get_dict()
    reviews_data = []
    for index, review in enumerate(reviews):
        review.spot
        dive_shop = review.dive_shop
        review_data = review.get_dict()
        review_data["spot"] = review.spot.get_dict()
        if dive_shop:
            review_data["dive_shop"] = dive_shop.get_simple_dict()
        if not review_data.get("title"):
            review_data["title"] = review.spot.name
        title = review_data["title"]
        review_data["title"] = f"#{len(reviews) - index} - {title}"
        image_data = []
        for image in review.images:
            image_data.append(image.get_dict())
        review_data["images"] = image_data
        reviews_data.append(review_data)
    user_data["reviews"] = reviews_data
    return {"data": user_data}


@bp.route("/profile_pic", methods=["POST"])
@jwt_required()
def upload():
    if "file" not in request.files:
        abort(422, "No file included in request")
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    file = request.files.get("file")
    if file.filename == "":
        abort(422, "Submitted an empty file")

    user = get_current_user()

    import uuid

    s3_key = str(get_current_user().id) + "_" + str(uuid.uuid4())
    if user.username:
        s3_key = user.username

    contents = file.read()
    bucket = os.environ.get("S3_BUCKET_NAME")
    s3_url = boto3.client("s3").upload_fileobj(
        io.BytesIO(contents),
        bucket,
        "profile_pic/" + s3_key,
        ExtraArgs={"ACL": "public-read", "ContentType": file.content_type},
    )
    s3_url = f"https://{bucket}.s3.amazonaws.com/profile_pic/{s3_key}"

    user = User.query.get_or_404(user.id)
    setattr(user, "profile_pic", s3_url)
    db.session.commit()

    return {"data": s3_url}


@bp.route("/wallet", methods=["GET"])
@jwt_required()
def get_user_wallet():
    # TODO: Implement fetch_user_wallet function
    # user = get_current_user()
    # wallet_data = fetch_user_wallet(user.id)
    # return {"data": wallet_data}
    return {"data": {"wallet": "not implemented yet"}}


@bp.route("/push_token", methods=["POST"])
@jwt_required()
def register_token():
    token = request.json.get("token")
    user = get_current_user()
    setattr(user, "push_token", token)
    db.session.commit()
    user.id

    return {"data": user.get_dict()}


@bp.route("/send_push", methods=["GET"])
def send_push():
    latitude = 40.73948410775358
    longitude = -73.99330617953866
    return send_notification(latitude, longitude, "test", "test")
