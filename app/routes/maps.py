import hashlib
import io
import os

import boto3
import requests
from botocore.exceptions import ClientError
from flask import Blueprint, abort, request, send_file

from app import cache

bp = Blueprint("maps", __name__, url_prefix="/maps")


def get_s3_client():
    """Get S3 client with proper configuration."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
    )


def generate_map_key(latitude, longitude, size="600x300", scale="2", maptype="terrain"):
    """Generate a unique S3 key for the map based on parameters."""
    # Create a hash of the parameters to ensure uniqueness
    params_string = f"{latitude}_{longitude}_{size}_{scale}_{maptype}"
    hash_object = hashlib.md5(params_string.encode())
    return f"maps/{hash_object.hexdigest()}.png"


def check_s3_map_exists(s3_key):
    """Check if a map already exists in S3."""
    try:
        s3_client = get_s3_client()
        bucket_name = os.environ.get("S3_BUCKET_NAME")
        s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        return True
    except ClientError:
        return False


def get_s3_map_url(s3_key):
    """Get the public URL for a map stored in S3."""
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"


def upload_map_to_s3(map_data, s3_key):
    """Upload map data to S3."""
    try:
        s3_client = get_s3_client()
        bucket_name = os.environ.get("S3_BUCKET_NAME")

        s3_client.upload_fileobj(
            io.BytesIO(map_data), bucket_name, s3_key, ExtraArgs={"ACL": "public-read", "ContentType": "image/png"}
        )
        return True
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return False


def fetch_google_maps_image(latitude, longitude, size="600x300", scale="2", maptype="terrain"):
    """Fetch static map image from Google Maps API."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    # Build the Google Maps Static API URL
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "size": size,
        "scale": scale,
        "maptype": maptype,
        "key": google_api_key,
        "style": "feature:poi|visibility:off",
        "markers": f"color:blue|label:1|{latitude},{longitude}",
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch map from Google Maps API: {e}")


@bp.route("/static")
@cache.cached(query_string=True)
def get_static_map():
    """Get Static Map
    ---
    get:
        summary: Get a static map image from Google Maps
        description: Returns a static map image for the given coordinates, with S3 caching to avoid repeated API calls
        parameters:
            - name: latitude
              in: query
              description: Latitude coordinate
              type: number
              required: true
            - name: longitude
              in: query
              description: Longitude coordinate
              type: number
              required: true
            - name: size
              in: query
              description: Map size (default: 600x300)
              type: string
              required: false
            - name: scale
              in: query
              description: Map scale (default: 2)
              type: string
              required: false
            - name: maptype
              in: query
              description: Map type (default: terrain)
              type: string
              required: false
        responses:
            200:
                description: Returns the map image
                content:
                  image/png:
                    schema:
                      type: string
                      format: binary
            400:
                description: Invalid parameters
            500:
                description: Server error
    """
    # Get parameters from query string
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    size = request.args.get("size", "600x300")
    scale = request.args.get("scale", "2")
    maptype = request.args.get("maptype", "terrain")

    # Validate required parameters
    if latitude is None or longitude is None:
        abort(400, description="latitude and longitude are required")

    # Validate latitude and longitude ranges
    if not (-90 <= latitude <= 90):
        abort(400, description="latitude must be between -90 and 90")
    if not (-180 <= longitude <= 180):
        abort(400, description="longitude must be between -180 and 180")

    # Generate S3 key for caching
    s3_key = generate_map_key(latitude, longitude, size, scale, maptype)

    # Check if map already exists in S3
    if check_s3_map_exists(s3_key):
        # Return the S3 URL for the cached map
        map_url = get_s3_map_url(s3_key)
        return {"url": map_url, "cached": True}

    try:
        # Fetch map from Google Maps API
        map_data = fetch_google_maps_image(latitude, longitude, size, scale, maptype)

        # Upload to S3 for caching
        if upload_map_to_s3(map_data, s3_key):
            # Return the S3 URL
            map_url = get_s3_map_url(s3_key)
            return {"url": map_url, "cached": False}
        else:
            # If S3 upload fails, return the image data directly
            return send_file(io.BytesIO(map_data), mimetype="image/png", as_attachment=False)

    except Exception as e:
        abort(500, description=f"Failed to generate map: {str(e)}")
