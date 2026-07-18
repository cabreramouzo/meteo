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


def get_api_v1():
  # la subida de imagenes sigue siendo un endpoint v1.1
  cfg = get_twitter_cfg()
  auth = tweepy.OAuth1UserHandler(cfg['consumer_key'], cfg['consumer_secret'],
                                  cfg['access_token'], cfg['access_token_secret'])
  return tweepy.API(auth)
