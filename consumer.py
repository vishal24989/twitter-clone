# consumer.py

import json
import time
import redis
from kafka import KafkaConsumer
from sqlalchemy.orm import sessionmaker, Session
from app.database import engine
from app.models import User
from app.cache import cache

print("Consumer service starting...")
time.sleep(15) # Wait for Kafka/DB/Redis to be ready

# Setup connections
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db: Session = SessionLocal()

print("Consumer connected to DB and Cache.")

def get_followers(author_id: int):
    """Finds all users who follow the author."""
    author = db.query(User).filter(User.id == author_id).first()
    if author:
        return author.followers
    return []

def fan_out_tweet(tweet_data: dict):
    """Writes a tweet to the Redis timeline cache of every follower."""
    author_id = tweet_data['author_id']
    tweet_id = tweet_data['tweet_id']
    
    followers = get_followers(author_id)
    
    print(f"Found {len(followers)} followers for author {author_id}. Fanning out tweet {tweet_id}.")

    for follower in followers:
        timeline_key = f"timeline:{follower.id}"
        # Add the new tweet ID to the top of the follower's timeline list
        cache.lpush(timeline_key, tweet_id)
        # Optional: Trim the timeline to keep it at a reasonable size (e.g., 1000 tweets)
        cache.ltrim(timeline_key, 0, 999)

    # Also, add the tweet to the author's own timeline
    author_timeline_key = f"timeline:{author_id}"
    cache.lpush(author_timeline_key, tweet_id)
    cache.ltrim(author_timeline_key, 0, 999)
    print(f"Fan-out for tweet {tweet_id} complete.")


def process_messages():
    consumer = KafkaConsumer(
        'new_tweets',
        bootstrap_servers=['kafka:9092'],
        auto_offset_reset='earliest',
        group_id='timeline-generator-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    print("Consumer waiting for messages...")
    
    for message in consumer:
        print(f"Received: {message.value}")
        fan_out_tweet(message.value)


if __name__ == "__main__":
    process_messages()