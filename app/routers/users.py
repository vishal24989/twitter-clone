from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta

from .. import database, models, schemas, security
from ..cache import cache

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/signup", response_class=HTMLResponse)
async def get_signup_form(request: Request, current_user: models.User = Depends(security.try_get_current_user)):
    """Serves the signup page, redirecting if user is already logged in."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup", response_class=HTMLResponse)
async def post_signup_form(request: Request, db: Session = Depends(database.get_db), username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    """Handles user registration."""
    db_user = db.query(models.User).filter((models.User.username == username) | (models.User.email == email)).first()
    if db_user:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Username or email already exists."})

    hashed_password = security.get_password_hash(password)
    new_user = models.User(username=username, email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login?message=Signup+successful!+Please+log+in.", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/login", response_class=HTMLResponse)
async def get_login_form(request: Request, current_user: models.User = Depends(security.try_get_current_user)):
    """Serves the login page, redirecting if user is already logged in."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def post_login_form(response: Response, db: Session = Depends(database.get_db), username: str = Form(...), password: str = Form(...)):
    """Handles user login, creating and setting a JWT cookie."""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not security.verify_password(password, user.hashed_password):
         return RedirectResponse(url="/login?error=Invalid+credentials", status_code=status.HTTP_303_SEE_OTHER)
        
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.get("/logout", response_class=HTMLResponse)
async def logout(response: Response):
    """Logs the user out by deleting the cookie."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response

@router.get("/users", response_class=HTMLResponse)
async def get_users_list(request: Request, db: Session = Depends(database.get_db), current_user: models.User = Depends(security.try_get_current_user)):
    """Serves a page listing all users and their follow status."""
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    following_ids = {user.id for user in current_user.followed}
    
    all_users = db.query(models.User).filter(models.User.id != current_user.id).all()
    
    return templates.TemplateResponse("users_list.html", {
        "request": request,
        "current_user": current_user,
        "all_users": all_users,
        "following_ids": following_ids
    })

@router.post("/follow/{user_id}", response_class=Response)
async def follow_user(user_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(security.get_current_user)):
    """Follows a user and backfills their timeline."""
    user_to_follow = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_follow:
        raise HTTPException(status_code=404, detail="User not found")

    if not current_user.is_following(user_to_follow):
        # 1. Create the follow relationship
        current_user.followed.append(user_to_follow)
        db.commit()

        # 2. Backfill the new follower's timeline
        recent_tweets = db.query(models.Tweet).filter(
            models.Tweet.author_id == user_to_follow.id
        ).order_by(models.Tweet.created_at.desc()).limit(100).all()
        
        if recent_tweets:
            timeline_key = f"timeline:{current_user.id}"
            tweet_ids_to_add = [tweet.id for tweet in recent_tweets]
            cache.lpush(timeline_key, *tweet_ids_to_add)
            cache.ltrim(timeline_key, 0, 999)

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/unfollow/{user_id}", response_class=Response)
async def unfollow_user(user_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(security.get_current_user)):
    """Unfollows a user and removes their tweets from the timeline cache."""
    user_to_unfollow = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_unfollow:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.is_following(user_to_unfollow):
        # --- KEY CHANGE: Add logic to remove tweets from cache ---
        
        # 1. Get all tweet IDs authored by the user we are about to unfollow.
        tweets_to_remove_ids = [
            tweet.id for tweet in user_to_unfollow.tweets
        ]
        
        # 2. Remove the follow relationship from the database.
        current_user.followed.remove(user_to_unfollow)
        db.commit()

        # 3. If there are tweet IDs to remove, delete them from the Redis cache.
        if tweets_to_remove_ids:
            timeline_key = f"timeline:{current_user.id}"
            # Loop through each ID and remove all of its occurrences from the Redis list.
            for tweet_id in tweets_to_remove_ids:
                cache.lrem(timeline_key, 0, tweet_id)

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile/{username}", response_class=HTMLResponse)
async def get_user_profile(
    request: Request,
    username: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.try_get_current_user)
):
    """Displays a user's profile and their tweets."""
    profile_user = db.query(models.User).filter(models.User.username == username).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_tweets = db.query(models.Tweet).filter(models.Tweet.author_id == profile_user.id).order_by(models.Tweet.created_at.desc()).all()

    is_following = False
    if current_user and current_user.id != profile_user.id:
        is_following = current_user.is_following(profile_user)
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "profile_user": profile_user,
        "user_tweets": user_tweets,
        "current_user": current_user,
        "is_following": is_following
    })

@router.get("/{username}/following", response_class=HTMLResponse)
async def get_following_page(
    request: Request,
    username: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.try_get_current_user)
):
    """Displays a list of users that the given user is following."""
    profile_user = db.query(models.User).filter(models.User.username == username).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # The 'followed' relationship gives us the list directly
    following_list = profile_user.followed
    
    return templates.TemplateResponse("following_list.html", {
        "request": request,
        "current_user": current_user,
        "profile_user": profile_user,
        "following_list": following_list
    })

@router.get("/{username}/followers", response_class=HTMLResponse)
async def get_followers_page(
    request: Request,
    username: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.try_get_current_user)
):
    """Displays a list of users who follow the given user."""
    profile_user = db.query(models.User).filter(models.User.username == username).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # The 'followers' backref gives us the list directly
    followers_list = profile_user.followers

    return templates.TemplateResponse("followers_list.html", {
        "request": request,
        "current_user": current_user,
        "profile_user": profile_user,
        "followers_list": followers_list
    })