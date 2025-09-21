# app/main.py
from fastapi import FastAPI
from app.routes.rankings import router as rankings_router
from app.routes.callback import router as callback_router
from app.routes.season_rankings import router as season_rankings_router

app = FastAPI(title="Fantasy Power Rankings API")

app.include_router(rankings_router)
app.include_router(callback_router)
app.include_router(season_rankings_router)

@app.get("/")
def root():
    return {"message": "Fantasy Power Rankings API is live!"}