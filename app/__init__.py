from __future__ import print_function

import json
import logging
import os
import os.path
from datetime import datetime, timedelta, timezone

import boto3
import newrelic.agent
import requests
from amplitude import Amplitude, BaseEvent
from botocore.exceptions import ClientError

# Load environment variables from .env file
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, request
from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_current_user,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
)
from flask_migrate import Migrate
from sendgrid import SendGridAPIClient
from sqlalchemy import and_, not_
from werkzeug.exceptions import HTTPException

from app.config import config
from app.models import AreaOne, AreaTwo, Country, Image, Spot, User, db
from app.scripts.openapi import spec

load_dotenv()

# Extensions (init without app)
cors = CORS()
cache = Cache()
jwtManager = JWTManager()
migrate = Migrate(compare_type=True)


# Helper functions (moved outside create_app to avoid circular imports)
def get_summary_reviews_helper(beach_id):
    from app.models import Review

    reviews = (
        db.session.query(db.func.count(Review.rating), Review.rating)
        .filter_by(beach_id=beach_id)
        .group_by(Review.rating)
        .all()
    )
    # average = db.session.query(db.func.avg(Review.rating)).filter_by(beach_id=beach_id).first()
    output = {}
    for review in reviews:
        output[str(review[1])] = review[0]
    # output["average"] = average[0][0]
    for i in range(1, 6):
        num = str(i)
        try:
            output[num]
        except KeyError:
            output[num] = 0

    return output


# --- APP FACTORY ---
def create_app(config_name=None, config_object=None):
    if config_object is not None:
        app_config = config_object
    else:
        config_name = config_name or os.environ.get("FLASK_ENV", "development")
        app_config_class = config.get(config_name, config["default"])
        app_config = app_config_class()

    app = Flask(__name__)
    app.config.from_object(app_config)

    # Set up logging
    if __name__ != "__main__":
        gunicorn_logger = logging.getLogger("gunicorn.error")
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    cors.init_app(app)
    cache.init_app(app)
    jwtManager.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # JWT user loader
    @jwtManager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        user_id = jwt_data["sub"]
        return User.query.filter_by(id=user_id).one_or_none()

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            return response

    @app.before_request
    def capture_request_params():
        if not app.config.get("DEBUG", False):
            newrelic.agent.capture_request_params()

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        response = e.get_response()
        response.data = json.dumps(
            {
                "code": e.code,
                "name": e.name,
                "msg": e.description,
            }
        )
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        newrelic.agent.record_exception(e)
        app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        response = jsonify(
            {
                "code": 500,
                "name": "Internal Server Error",
                "msg": "An unexpected error occurred. Please try again later.",
            }
        )
        response.status_code = 500
        return response

    @app.route("/")
    def home_view():
        client = Amplitude(os.environ.get("AMPLITUDE_API_KEY"))
        client.configuration.min_id_length = 1
        event = BaseEvent(event_type="health_check", user_id="1")
        client.track(event)
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "checks": {},
        }
        try:
            db.session.execute("SELECT 1")
            health_status["checks"]["database"] = "healthy"
        except Exception as e:
            health_status["checks"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
            newrelic.agent.record_exception(e)
        try:
            cache.set("health_check", "ok", timeout=10)
            cache_value = cache.get("health_check")
            if cache_value == "ok":
                health_status["checks"]["cache"] = "healthy"
            else:
                health_status["checks"]["cache"] = "unhealthy: cache not working"
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["cache"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
            newrelic.agent.record_exception(e)
        try:
            if os.environ.get("SENDGRID_API_KEY"):
                health_status["checks"]["sendgrid"] = "configured"
            else:
                health_status["checks"]["sendgrid"] = "not_configured"
        except Exception as e:
            health_status["checks"]["sendgrid"] = f"error: {str(e)}"
        status_code = 200 if health_status["status"] == "healthy" else 503
        return jsonify(health_status), status_code

    @app.route("/health/ready")
    def readiness_check():
        try:
            db.session.execute("SELECT 1")
            return jsonify({"status": "ready"}), 200
        except Exception as e:
            newrelic.agent.record_exception(e)
            return jsonify({"status": "not_ready", "error": str(e)}), 503

    @app.route("/health/live")
    def liveness_check():
        return jsonify({"status": "alive"}), 200

    @app.route("/db")
    def db_create():
        db.create_all()
        return "<h1>Welcome to Zentacle</h1>"

    @app.route("/delete")
    @jwt_required()
    def delete():
        user = get_current_user()
        if not user.admin:
            abort(403, "You must be an admin to that")
        email = request.args.get("email")
        user_to_delete = User.query.filter_by(email=email).first()
        if not user_to_delete:
            abort(404, "User not found")
        db.session.delete(user_to_delete)
        db.session.commit()
        return {"msg": "User deleted successfully"}

    @app.route("/getall/email")
    @jwt_required()
    def get_emails():
        if not get_current_user().admin:
            abort(403, "You must be an admin to that")
        users = User.query.filter(and_(not_(User.email.contains("zentacle.com")), User.is_fake.is_not(True)))
        output = []
        for user in users:
            data = {
                "email": user.email,
                "first_name": user.first_name,
                "display_name": user.display_name,
                "id": user.id,
            }
            output.append(data)
        return {"data": output}

    @app.route("/refresh")
    @jwt_required(refresh=True)
    def refresh_token():
        """Refresh auth token
        ---
        get:
            summary: Refresh auth token
            description: Refresh auth token
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
        user_id = get_jwt_identity()
        auth_token = create_access_token(identity=user_id)
        return jsonify(auth_token=auth_token)

    @app.route("/beachimages")
    @cache.cached(query_string=True)
    def get_beach_images():
        beach_id = request.args.get("beach_id")
        output = []
        images = Image.query.filter_by(beach_id=beach_id).all()
        for image in images:
            dictionary = image.get_dict()
            dictionary["signedurl"] = dictionary["url"]
            output.append(dictionary)
        return {"data": output}

    @app.route("/reviewimages")
    @cache.cached(query_string=True)
    def get_review_images():
        review_id = request.args.get("review_id")
        output = []
        images = Image.query.filter_by(review_id=review_id).all()
        for image in images:
            dictionary = image.get_dict()
            dictionary["signedurl"] = dictionary["url"]
            output.append(dictionary)
        return {"data": output}

    @app.route("/s3-upload")
    def create_presigned_post():
        bucket_name = os.environ.get("S3_BUCKET_NAME")
        object_name = request.args.get("file")
        expiration = 3600

        # Generate a presigned S3 POST URL
        s3_client = boto3.client("s3", region_name="us-east-1")
        try:
            response = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=object_name,
                ExpiresIn=expiration,
                Fields={
                    "acl": "public-read",
                },
                Conditions=[
                    {
                        "acl": "public-read",
                    }
                ],
            )
        except ClientError as e:
            logging.error(e)
            return None

        # The response contains the presigned URL and required fields
        return response

    @app.route("/set-country")
    def set_country():
        country_id = request.args.get("country_id")
        country_short_name = request.args.get("country_short_name")
        area_one_id = request.args.get("area_one_id")
        area_one_short_name = request.args.get("area_one_short_name")
        area_two_id = request.args.get("area_two_id")
        area_two_short_name = request.args.get("area_two_short_name")
        locality_id = request.args.get("locality_id")
        region_url = request.args.get("region_url")
        destination_url = request.args.get("destination_url")
        if region_url:
            spots = Spot.query.filter(Spot.shorediving_data.has(region_url=region_url)).all()
        elif destination_url:
            spots = Spot.query.filter(Spot.shorediving_data.has(destination_url=destination_url)).all()
        else:
            abort(401, "No destination or region")
        if country_short_name:
            country = Country.query.filter_by(short_name=country_short_name).first()
            country_id = country.id
        if area_one_short_name:
            area_one = AreaOne.query.filter_by(short_name=area_one_short_name).first()
            area_one_id = area_one.id
        if area_two_short_name:
            area_two = AreaTwo.query.filter_by(short_name=area_two_short_name).first()
            area_two_id = area_two.id
        data = []
        for spot in spots:
            if not spot.country_id and country_id:
                spot.country_id = int(country_id)
            if not spot.area_one_id and area_one_id:
                spot.area_one_id = int(area_one_id)
            if not spot.area_two_id and area_two_id:
                spot.area_two_id = int(area_two_id)
            if not spot.locality_id and locality_id:
                spot.locality_id = int(locality_id)
            data.append(spot.get_dict())
        db.session.commit()
        return {"data": data}

    @app.route("/update-usernames")
    def update_usernames():
        users = User.query.filter(
            and_(
                User.registered_on > "2021-09-11 09:45:43.152087",
                User.registered_on < "2021-09-11 20:26:26.295655",
            )
        )

        output = []
        failed = []
        for user in users:
            if "-" in user.username:
                old_username = user.username
                new_username = user.username.replace("-", "_")
                user.username = new_username
                output.append(
                    {
                        "id": user.id,
                        "old_username": old_username,
                        "new_username": new_username,
                    }
                )
                try:
                    db.session.commit()
                except Exception:
                    failed.append(user.get_dict())
        return {
            "data": output,
            "failed": failed,
        }

    @app.route("/spec")
    def get_apispec():
        return jsonify(spec.to_dict())

    @app.route("/subscription-webhook", methods=["POST"])
    def subscription_webhook():
        event = request.json.get("event")
        event_type = event.get("type")
        user_id = int(event.get("app_user_id"))
        user = User.query.filter_by(id=user_id).first_or_404()

        if event_type == "INITIAL_PURCHASE" or event_type == "RENEWAL" or event_type == "UNCANCELLATION":
            setattr(user, "has_pro", True)

            # Add to SendGrid contacts
            sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
            data = {
                "contacts": [
                    {
                        "email": user.email,
                        "custom_fields": {
                            "e2_T": "True",
                        },
                    }
                ],
                "list_ids": ["3d67ca05-8e79-4a44-9bce-a6004b58024e"],
            }

            try:
                sg.client.marketing.contacts.put(request_body=data)
            except Exception as e:
                print(f"Error adding to SendGrid contacts: {e}")

            # Schedule welcome email and trial reminder
            try:
                from app.helpers.email_scheduler import schedule_trial_reminder_email, schedule_welcome_email

                # Schedule welcome email (immediate)
                schedule_welcome_email(user_id)

                # Schedule trial reminder email (6 days later)
                schedule_trial_reminder_email(user_id)

            except Exception as e:
                print(f"Error scheduling emails: {e}")

        elif event_type == "CANCELLATION" or event_type == "EXPIRATION" or event_type == "SUBSCRIPTION_PAUSED":
            setattr(user, "has_pro", False)

            # Cancel any pending trial reminder emails
            try:
                from app.helpers.email_scheduler import cancel_scheduled_emails

                cancel_scheduled_emails(user_id, "trial_reminder")
            except Exception as e:
                print(f"Error canceling scheduled emails: {e}")

        db.session.commit()

        return "OK"

    @app.route("/payment-link")
    def payment():
        try:
            email = request.args.get("email")
            user = User.query.filter_by(email=email).first()
            user_id = user.id if user else None
            payment_link = os.environ.get("STRIPE_PAYMENT_LINK")
            return redirect(
                f"{payment_link}?prefilled_email={email}&client_reference_id={user_id}",
                code=302,
            )
        except Exception:
            raise Exception("Unable to create payment intent")

    @app.route("/stripe-webhook", methods=["POST"])
    def stripe_webhook():
        import stripe

        event = None
        payload = request.data
        sig_header = request.headers["STRIPE_SIGNATURE"]

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, os.environ.get("STRIPE_ENDPOINT_SECRET"))
        except ValueError as e:
            # Invalid payload
            raise e
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise e
        if event.type == "checkout.session.completed":
            object = event.data.object
            client_reference_id = object.get("client_reference_id")
            if client_reference_id:
                subscription = object.get("subscription")
                revenuecat_api_key = os.environ.get("REVENUECAT_API_KEY")
                response = requests.post(
                    "https://api.revenuecat.com/v1/receipts",
                    headers={
                        "X-Platform": "stripe",
                        "Authorization": f"Bearer {revenuecat_api_key}",
                    },
                    json={
                        "app_user_id": client_reference_id,
                        "fetch_token": subscription,
                    },
                )
                if response.ok:
                    return jsonify(success=True)
                else:
                    return jsonify(response.json()), response.status_code
        return jsonify(success=True)

    @app.route("/subsurface")
    def subsurface():
        username = request.args.get("username")
        password = request.args.get("password")
        import requests

        url = f"https://cloud.subsurface-divelog.org/user/{username}/dives.html_files/file.js"

        import base64

        message_bytes = f"{username}:{password}".encode()
        base64_bytes = base64.b64encode(message_bytes)
        auth_token = base64_bytes.decode("ascii")
        payload = {}
        headers = {"Authorization": f"Basic {auth_token}"}

        response = requests.request("GET", url, headers=headers, data=payload)

        import json

        return jsonify(json.loads(response.text[6:])[0])

    from app.routes import shop as shop_routes

    app.register_blueprint(shop_routes.bp)

    from app.routes import user as user_routes

    app.register_blueprint(user_routes.bp)

    from app.routes import users as users_routes

    app.register_blueprint(users_routes.bp)

    from app.routes import review as review_routes

    app.register_blueprint(review_routes.bp)

    from app.routes import reviews as reviews_routes

    app.register_blueprint(reviews_routes.bp)

    from app.routes import buddy as buddy_routes

    app.register_blueprint(buddy_routes.bp)

    from app.routes import spots as spots_routes

    app.register_blueprint(spots_routes.bp)

    from app.routes import spot as spot_routes

    app.register_blueprint(spot_routes.bp)

    from app.routes import search as search_routes

    app.register_blueprint(search_routes.bp)

    from app.routes import loc as loc_routes

    app.register_blueprint(loc_routes.bp)

    from app.routes import locality as locality_routes

    app.register_blueprint(locality_routes.bp)

    from app.routes import password as password_routes

    app.register_blueprint(password_routes.bp)

    # Register new geographic routing system
    from app.routes import geography

    app.register_blueprint(geography.bp)

    # CLI Commands
    @app.cli.command("process-emails")
    def process_emails():
        """Process all due scheduled emails"""
        from app.helpers.email_scheduler import process_due_emails

        print("Processing scheduled emails...")
        result = process_due_emails()

        print(f"Processed {result['total_processed']} emails:")
        print(f"  - Sent: {result['sent']}")
        print(f"  - Failed: {result['failed']}")

    @app.cli.command("check-scheduler-health")
    def check_scheduler_health():
        """Check if the email scheduler is running properly"""
        from app.helpers.email_scheduler import check_scheduler_health

        print("Checking scheduler health...")
        result = check_scheduler_health()

        print(f"Scheduler Health Check:")
        print(f"  - Overdue emails: {result['overdue_emails']}")
        print(f"  - Recent activity: {result['recent_activity']} emails in last 2 hours")
        print(f"  - Healthy: {result['healthy']}")

        if not result["healthy"]:
            exit(1)  # Exit with error code for monitoring

    with app.test_request_context():
        pass
        # spec.path(view=user_signup)
        # spec.path(view=user_apple_signup)
        # spec.path(view=user_google_signup)
        # spec.path(view=user_finish_signup)
        # spec.path(view=patch_user)
        # spec.path(view=user_login)
        # spec.path(view=get_spots)
        # spec.path(view=add_review)
        # spec.path(view=get_reviews)
        # spec.path(view=get_user)
        # spec.path(view=get_recs)
        # spec.path(view=nearby_locations)
        # spec.path(view=get_typeahead)
        # spec.path(view=patch_review)
        # spec.path(view=patch_spot)
        # spec.path(view=search_spots)
        # spec.path(view=get_review)
        # spec.path(view=upload_file)
        # spec.path(view=get_recent_reviews)
        # ...

    return app


# For legacy imports
app = create_app()
