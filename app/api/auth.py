from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from app.services.auth_service import AuthService

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()

    result, status_code = AuthService.create_user(
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        email=data.get('email'),
        username=data.get('username'),
        profile_pic=data.get('profile_pic'),
        password=data.get('password'),
        phone=data.get('phone'),
        app_name=data.get('app')
    )

    response = jsonify(result)
    if status_code == 200:
        set_access_cookies(response, result['access_token'])
        set_refresh_cookies(response, result['refresh_token'])

    return response, status_code


@bp.route('/login', methods=['POST'])
def login():
    """Login with email and password."""
    data = request.get_json()

    result, status_code = AuthService.authenticate_user(
        email=data.get('email'),
        password=data.get('password')
    )

    response = jsonify(result)
    if status_code == 200:
        set_access_cookies(response, result['access_token'])
        set_refresh_cookies(response, result['refresh_token'])

    return response, status_code


@bp.route('/google', methods=['POST'])
def google_login():
    """Login with Google ID token."""
    data = request.get_json()

    result, status_code = AuthService.authenticate_google_user(
        id_token_str=data.get('id_token')
    )

    response = jsonify(result)
    if status_code == 200:
        set_access_cookies(response, result['access_token'])
        set_refresh_cookies(response, result['refresh_token'])

    return response, status_code


@bp.route('/apple', methods=['POST'])
def apple_login():
    """Login with Apple ID token."""
    data = request.get_json()

    result, status_code = AuthService.authenticate_apple_user(
        id_token_str=data.get('id_token'),
        audience=data.get('audience')
    )

    response = jsonify(result)
    if status_code == 200:
        set_access_cookies(response, result['access_token'])
        set_refresh_cookies(response, result['refresh_token'])

    return response, status_code


@bp.route('/logout', methods=['POST'])
def logout():
    """Logout user."""
    response = jsonify({"message": "Logged out successfully"})
    unset_jwt_cookies(response)
    return response


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)

    response = jsonify({"access_token": access_token})
    set_access_cookies(response, access_token)
    return response