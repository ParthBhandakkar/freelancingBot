import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import leads, analytics, search

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lead Finder Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(analytics.router)
app.include_router(search.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
