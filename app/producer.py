from kafka import KafkaProducer, errors
import json
import time

KAFKA_SERVER = 'kafka:9092'
producer = None

# Retry connecting to Kafka
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_SERVER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("Kafka Producer connected successfully.")
    except errors.NoBrokersAvailable:
        print("Waiting for Kafka broker to be available...")
        time.sleep(5)

def send_tweet_to_kafka(tweet_data: dict):
    """
    Sends tweet data to the 'new_tweets' Kafka topic.
    """
    try:
        producer.send('new_tweets', value=tweet_data)
        # Flush ensures all buffered messages are sent to the broker.
        producer.flush()
        print(f"Sent tweet to Kafka: {tweet_data}")
    except Exception as e:
        print(f"Error sending to Kafka: {e}")