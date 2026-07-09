import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from ..database import get_db
from ..models import Lead
from ..schemas import LeadCreate, LeadUpdate, LeadOut
from ..services.lead_finder import calc_lead_potential

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("", response_model=list[LeadOut])
def list_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    platform: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    sort_by: Optional[str] = "created_at",
    sort_dir: Optional[str] = "desc",
    db: Session = Depends(get_db),
):
    query = db.query(Lead)
    if status:
        query = query.filter(Lead.status == status)
    if platform:
        query = query.filter(Lead.platform == platform)
    if search:
        query = query.filter(
            Lead.name.ilike(f"%{search}%")
            | Lead.business_name.ilike(f"%{search}%")
            | Lead.city.ilike(f"%{search}%")
            | Lead.niche.ilike(f"%{search}%")
        )
    if min_score is not None:
        query = query.filter(Lead.lead_score >= min_score)

    sort_col = getattr(Lead, sort_by, Lead.created_at)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    return query.offset(skip).limit(limit).all()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("", response_model=LeadOut)
def create_lead(data: LeadCreate, db: Session = Depends(get_db)):
    if data.website_url:
        existing = db.query(Lead).filter(
            Lead.website_url.ilike(data.website_url.strip())
        ).first()
        if existing:
            logger.warning("Duplicate lead rejected (website): %s (%s)", data.business_name, data.website_url)
            raise HTTPException(status_code=409, detail=f"Lead with website '{data.website_url}' already exists (id={existing.id})")
    else:
        name = (data.business_name or data.name or "").strip()
        city = (data.city or "").strip()
        if name:
            dup = db.query(Lead).filter(Lead.business_name.ilike(name))
            if city:
                dup = dup.filter(Lead.city.ilike(city))
            existing = dup.first()
            if existing:
                logger.warning("Duplicate lead rejected (name+city): %s / %s", name, city)
                raise HTTPException(status_code=409, detail=f"Lead '{data.business_name}' in '{data.city}' already exists (id={existing.id})")
    lead = Lead(**data.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    biz_dict = {"name": lead.name, "website_url": lead.website_url or "", "phone": lead.phone or "", "email": lead.email or "", "total_ratings": data.total_ratings or 0, "rating": data.rating or 0.0, "types": [], "address": lead.address or lead.city or ""}
    potential = calc_lead_potential(biz_dict)
    lead.lead_score = potential["potential_score"]
    lead.intent_signals = ", ".join(potential["signals"])
    db.commit()
    db.refresh(lead)
    logger.info("Created lead #%s: %s (score=%s)", lead.id, lead.business_name, lead.lead_score)
    return lead


@router.put("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"message": "Lead deleted"}


@router.get("/batch/delete")
def batch_delete_leads(ids: str = Query(..., description="Comma-separated lead IDs")):
    return {"message": "Use DELETE with individual IDs"}


@router.post("/export/sheets")
def export_to_google_sheets(db: Session = Depends(get_db)):
    from ..services.google_sheets import export_leads_to_sheet
    sheet_id = os.getenv("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        logger.error("Export failed: GOOGLE_SHEETS_ID not set")
        return {"success": False, "error": "GOOGLE_SHEETS_ID not set in .env"}
    logger.info("Exporting %d leads to sheet %s", db.query(Lead).count(), sheet_id)
    result = export_leads_to_sheet(sheet_id, db)
    if result.get("success"):
        logger.info("Export successful: %d leads", result.get("total_leads"))
    else:
        logger.error("Export failed: %s", result.get("error"))
    return result
