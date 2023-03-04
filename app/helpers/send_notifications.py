import boto3
from app.models import User

def send_notification(latitude, longitude, title, message):
    nearby_users = User.query \
        .filter(User.distance(latitude, longitude) < 1) \
        .all()
    for user in nearby_users:
        if user.push_token:
            send_push_notification(user.push_token, title, message)
        send_email(user.email, message)
    return 'ok'

def send_email(email, message):
    return email, message

def send_push_notification(push_token, title, message):
    response = boto3.client('pinpoint').send_messages(
        ApplicationId='268df0f0464b49609f26f711a800aecd',
        MessageRequest={
            'Addresses': {
                f'{push_token}': {
                      'ChannelType': 'APNS',
                }
            },
            'MessageConfiguration': {
                'APNSMessage': {
                    'APNSPushType': 'alert',
                    'Action': 'OPEN_APP',  # | 'DEEP_LINK' | 'URL',
                    'Badge': 1,
                    'Body': message,
                    # 'Category': 'string',
                    # 'CollapseId': 'string',
                    # 'Data': {
                    #     'string': 'string'
                    # },
                    # 'MediaUrl': 'string',
                    # 'PreferredAuthenticationMethod': 'string',
                    # 'Priority': 'string',
                    # 'RawContent': 'string',
                    # 'SilentPush': True | False,
                    # 'Sound': 'string',
                    # 'Substitutions': {
                    #     'string': [
                    #         'string',
                    #     ]
                    # },
                    # 'ThreadId': 'string',
                    # 'TimeToLive': 123,
                    'Title': title,
                    # 'Url': 'string'
                },
            }
        }
    )
