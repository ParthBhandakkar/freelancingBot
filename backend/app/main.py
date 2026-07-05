import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import leads, analytics, search, analysis, outreach

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lead Finder Dashboard", version="2.0.0")
logger.info("Backend started")

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
app.include_router(analysis.router)
app.include_router(outreach.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
