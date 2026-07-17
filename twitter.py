import tweepy
from config import get_twitter_cfg


def get_client():
  cfg = get_twitter_cfg()
  return tweepy.Client(
    consumer_key=cfg['consumer_key'],
    consumer_secret=cfg['consumer_secret'],
    access_token=cfg['access_token'],
    access_token_secret=cfg['access_token_secret'],
  )
