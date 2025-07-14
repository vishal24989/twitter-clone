from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import models, database, security
from .routers import users, tweets
from .cache import cache

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(users.router)
app.include_router(tweets.router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.try_get_current_user)
):
    
    timeline = []
    if current_user:
        timeline_key = f"timeline:{current_user.id}"
        tweet_ids = cache.lrange(timeline_key, 0, 100)
        
        if tweet_ids:
            timeline = db.query(models.Tweet).filter(models.Tweet.id.in_(tweet_ids)).order_by(models.Tweet.created_at.desc()).all()
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "timeline": timeline
    })