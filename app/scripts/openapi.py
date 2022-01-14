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
class UserSchema(Schema):
    display_name = fields.Str()
    username = fields.Str()
    email = fields.Str()
    first_name = fields.Str()
    last_name = fields.Str()
    profile_pic = fields.Str()

class BeachSchema(Schema):
    display_name = fields.Str()

class ReviewSchema(Schema):
    text = fields.Str()

class TypeAheadSchema(Schema):
    text = fields.Str()
    id = fields.Int()
    type = fields.Str()
    url = fields.Str()
