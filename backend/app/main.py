import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from .routes import leads, analytics, search, analysis, outreach, settings
from .services.scheduler import start_scheduler

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

assets_dir = os.path.join(os.getcwd(), "generated_assets")
os.makedirs(assets_dir, exist_ok=True)
app.mount("/assets", StaticFiles(directory=assets_dir, html=True), name="assets")

app.include_router(leads.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(analysis.router)
app.include_router(outreach.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    start_scheduler()
    logger.info("Startup complete: scheduler running")
