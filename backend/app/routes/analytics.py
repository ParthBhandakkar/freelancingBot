from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Lead
from ..schemas import DashboardStats

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(Lead).count()
    new_leads = db.query(Lead).filter(Lead.status == "new").count()
    contacted = db.query(Lead).filter(Lead.status == "contacted").count()
    responded = db.query(Lead).filter(Lead.response == "responded").count()
    converted = db.query(Lead).filter(Lead.response == "converted").count()
    assets = db.query(Lead).filter(Lead.asset_generated == True).count()
    avg_score = db.query(func.avg(Lead.online_presence_score)).scalar() or 0.0

    platforms = (
        db.query(Lead.platform, func.count(Lead.id))
        .group_by(Lead.platform)
        .all()
    )
    leads_by_platform = {p: c for p, c in platforms}

    statuses = (
        db.query(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
        .all()
    )
    leads_by_status = {s: c for s, c in statuses}

    cities = (
        db.query(Lead.city, func.count(Lead.id))
        .filter(Lead.city.isnot(None))
        .group_by(Lead.city)
        .order_by(func.count(Lead.id).desc())
        .limit(10)
        .all()
    )
    leads_by_city = [{"city": c, "count": n} for c, n in cities if c]

    return DashboardStats(
        total_leads=total,
        new_leads=new_leads,
        contacted=contacted,
        responded=responded,
        converted=converted,
        assets_generated=assets,
        avg_presence_score=round(float(avg_score), 1),
        leads_by_platform=leads_by_platform,
        leads_by_status=leads_by_status,
        leads_by_city=leads_by_city,
    )
