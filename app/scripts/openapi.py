from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from marshmallow import Schema, fields

# Create spec
spec = APISpec(
    title='Zentacle API',
    version='1.0.0',
    openapi_version="3.0.2",
    info=dict(
        description='Internal API for interacting with the Zentacle database'
    ),
    plugins=[
        FlaskPlugin(), MarshmallowPlugin()
    ]
)

# Reference your schemas definitions
class TagSchema(Schema):
    id = fields.Int()
    short_name = fields.Str()
    text = fields.Str()
    type = fields.Str()

class BeachSchema(Schema):
    name = fields.Str()
    id = fields.Int()
    description = fields.Str()
    location_city = fields.Str()
    num_reviews = fields.Int()
    rating = fields.Float()
    url = fields.Str()
    difficulty = fields.Str()
    entry_map = fields.Str()
    hero_img = fields.Str()
    location_google = fields.Str()
    access = fields.List(fields.Nested(TagSchema()))

class ReviewSchema(Schema):
    text = fields.Str()
    spot = fields.Nested(BeachSchema())
    date_dived = fields.Str()
    id = fields.Int()
    rating = fields.Float()
    activity_type = fields.Str()
    visibility = fields.Int()
class UserSchema(Schema):
    display_name = fields.Str()
    username = fields.Str()
    email = fields.Str()
    first_name = fields.Str()
    last_name = fields.Str()
    profile_pic = fields.Str()
    reviews = fields.List(fields.Nested(ReviewSchema()))

class TypeAheadSchema(Schema):
    text = fields.Str()
    id = fields.Int()
    type = fields.Str(description="Either 'location' (if it's a country, state, etc) or 'site' (if it's a specific dive site)")
    url = fields.Str()
    subtext = fields.Str()

class AppleRegisterSchema(Schema):
    id_token = fields.Str()
    code = fields.Str()
    user = fields.Dict()
    state = fields.Str()

class ImageUploadResponse(Schema):
    data: fields.Str()

class ImageUploadRequest(Schema):
    file: fields.Str()
