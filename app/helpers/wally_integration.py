import os
import string
import requests

from app.models import Review, User, DiveShop, Spot

wally_api_base = os.environ.get('WALLY_API')
wally_auth_token = os.environ.get('WALLY_AUTH_TOKEN')

def mint_nft(current_review: Review, dive_shop: DiveShop, beach: Spot, user: User, signature: string):
  payload = {
    'walletId': f'user_{str(user.id)}',
    'metadata': {
      'image': dive_shop.stamp_uri,
      'description': signature,
      'name': beach.name,
      'attributes': [
        {
          'trait_type': 'Dive Shop',
          'value': dive_shop.name
        },
        {
          'trait_type': 'Date Dived',
          'value': f'{current_review.date_dived}',
          'display_type': 'date'
        },
      ]
    }
  }


  request_url = f'{wally_api_base}/nfts/create/from-structured-metadata'
  headers = {
    'Authorization': f'Bearer {wally_auth_token}'
  }

  response = requests.post(request_url, headers=headers, json=payload)
  response.raise_for_status()
  data = response.json()
  return data

def create_wallet(user: User):
  request_url = f'{wally_api_base}/wallets/create'
  headers = {
    'Authorization': f'Bearer {wally_auth_token}',
    'Content-Type': 'application/json',
  }

  payload = {
    'id': f'user_{str(user.id)}',
    'email': user.email, # owner is the current user, so owner email is current user email
    'tags': ['user']
  }

  response = requests.post(request_url, headers=headers, json=payload)
  response.raise_for_status()
  data = response.json()
  return data

def sign_message(user: User, dive_shop: DiveShop):
  wallet_id = f'user_{str(user.id)}'
  request_url = f'{wally_api_base}/wallet/{wallet_id}/sign-message'
  payload = {
    "message": f'Dive log signed by {dive_shop.name}'
  }
  headers = {
    'Authorization': f'Bearer {wally_auth_token}',
    'Content-Type': 'application/json',
  }
  response = requests.post(request_url, headers=headers, json=payload)
  response.raise_for_status()
  data = response.json()
  return data
