from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import database, models, schemas, security, producer

# Setup router
router = APIRouter()

@router.post("/tweets", response_class=RedirectResponse)
async def create_tweet(
    text: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Handles new tweet creation.
    1. Saves the tweet to the database.
    2. Sends a message to Kafka for the fan-out service.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        
    # 1. Save tweet to the database (source of truth)
    new_tweet = models.Tweet(text=text, author_id=current_user.id)
    db.add(new_tweet)
    db.commit()
    db.refresh(new_tweet) # Refresh to get the new tweet's ID from the DB
    
    # 2. Send a message to Kafka for background fan-out processing
    tweet_data = {
        "tweet_id": new_tweet.id,
        "author_id": current_user.id,
        "text": new_tweet.text
    }
    producer.send_tweet_to_kafka(tweet_data)

    # Redirect the user back to the homepage
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)