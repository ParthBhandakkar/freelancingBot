from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Lead, OutreachTemplate, OutreachSequence, OutreachSequenceStep
from ..schemas import (
    OutreachTemplateCreate, OutreachTemplateUpdate, OutreachTemplateOut,
    OutreachSequenceCreate, OutreachSequenceOut, OutreachSequenceStepOut,
)
from ..services.email_service import render_template, send_email

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

VARIABLE_HELP = {
    "business_name": "Name of the business",
    "contact_name": "Name of the contact person",
    "city": "Business city",
    "niche": "Business niche/type",
    "flaws": "Identified issues with their online presence",
    "score": "Online presence score",
    "website": "Business website URL",
    "phone": "Business phone number",
    "my_name": "Your name (from SMTP_FROM_NAME)",
    "my_company": "Your company name",
}

DEFAULT_TEMPLATES = [
    {
        "name": "Initial Outreach - Website Issues",
        "description": "First contact pointing out specific website issues found",
        "subject": "Quick website feedback for {{business_name}}",
        "body": "Hi {{contact_name}},\n\nI recently came across {{business_name}} in {{city}} and noticed your website at {{website}}. I help local businesses improve their online presence.\n\nA few things I noticed:\n{{flaws}}\n\nI'd love to help you fix these. Would you be open to a quick 15-minute call this week?\n\nBest,\n{{my_name}}",
        "variables": ["business_name", "contact_name", "city", "website", "flaws", "my_name"],
        "channel": "email",
    },
    {
        "name": "Follow-up - Value Proposition",
        "description": "Follow-up email focusing on value proposition",
        "subject": "Following up - {{business_name}}",
        "body": "Hi {{contact_name}},\n\nJust following up on my previous message. I specialize in helping {{niche}} businesses in {{city}} grow their online presence.\n\nWith your current score of {{score}}/100, there's significant room for improvement that could bring more customers to {{business_name}}.\n\nI've helped similar businesses achieve great results. Happy to share examples.\n\nBest,\n{{my_name}}",
        "variables": ["business_name", "contact_name", "city", "niche", "score", "my_name"],
        "channel": "email",
    },
    {
        "name": "LinkedIn Connection Request",
        "description": "LinkedIn connection message",
        "subject": "Quick connect - {{business_name}}",
        "body": "Hi {{contact_name}}, I came across {{business_name}} and noticed areas where I could help improve your online presence. Would love to connect and share some ideas!",
        "variables": ["business_name", "contact_name"],
        "channel": "linkedin",
    },
    {
        "name": "Call Script",
        "description": "Phone call script for outreach",
        "subject": "Call Script",
        "body": "Hi {{contact_name}}, this is {{my_name}}. I was looking at {{business_name}}'s online presence and found a few things that might be costing you customers.\n\nSpecifically:\n- {{flaws}}\n\nI help {{niche}} businesses fix these issues. I'm calling to see if you'd be open to a quick chat?\n\nIf now's not a good time, when would work better?",
        "variables": ["business_name", "contact_name", "flaws", "niche", "my_name"],
        "channel": "call",
    },
]


@router.get("/templates", response_model=list[OutreachTemplateOut])
def list_templates(search: Optional[str] = None, channel: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(OutreachTemplate)
    if search:
        query = query.filter(
            OutreachTemplate.name.ilike(f"%{search}%")
            | OutreachTemplate.description.ilike(f"%{search}%")
        )
    if channel:
        query = query.filter(OutreachTemplate.channel == channel)
    return query.all()


@router.get("/templates/defaults")
def seed_default_templates(db: Session = Depends(get_db)):
    existing = db.query(OutreachTemplate).count()
    if existing > 0:
        return {"message": f"{existing} templates already exist, skipping seed"}
    for tmpl in DEFAULT_TEMPLATES:
        t = OutreachTemplate(**tmpl)
        db.add(t)
    db.commit()
    return {"message": f"Seeded {len(DEFAULT_TEMPLATES)} default templates"}


@router.get("/templates/{template_id}", response_model=OutreachTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


@router.post("/templates", response_model=OutreachTemplateOut)
def create_template(data: OutreachTemplateCreate, db: Session = Depends(get_db)):
    tmpl = OutreachTemplate(**data.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.put("/templates/{template_id}", response_model=OutreachTemplateOut)
def update_template(template_id: int, data: OutreachTemplateUpdate, db: Session = Depends(get_db)):
    tmpl = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(tmpl, key, value)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(OutreachTemplate).filter(OutreachTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tmpl)
    db.commit()
    return {"message": "Template deleted"}


@router.get("/variables")
def get_variables():
    return {"variables": VARIABLE_HELP}


@router.get("/sequences", response_model=list[OutreachSequenceOut])
def list_sequences(lead_id: Optional[int] = None, active: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(OutreachSequence)
    if lead_id:
        query = query.filter(OutreachSequence.lead_id == lead_id)
    if active is not None:
        query = query.filter(OutreachSequence.active == active)
    return query.all()


@router.get("/sequences/{seq_id}", response_model=OutreachSequenceOut)
def get_sequence(seq_id: int, db: Session = Depends(get_db)):
    seq = db.query(OutreachSequence).filter(OutreachSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return seq


@router.post("/sequences", response_model=OutreachSequenceOut)
def create_sequence(data: OutreachSequenceCreate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    steps_data = data.steps
    seq = OutreachSequence(lead_id=data.lead_id, name=data.name)
    db.add(seq)
    db.commit()
    db.refresh(seq)

    for step_data in steps_data:
        step = OutreachSequenceStep(
            sequence_id=seq.id,
            step_order=step_data.step_order,
            action_type=step_data.action_type,
            subject=step_data.subject,
            body=step_data.body,
            delay_days=step_data.delay_days,
        )
        db.add(step)
    db.commit()
    db.refresh(seq)
    return seq


@router.post("/sequences/{seq_id}/advance")
def advance_sequence(seq_id: int, db: Session = Depends(get_db)):
    seq = db.query(OutreachSequence).filter(OutreachSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    steps = db.query(OutreachSequenceStep).filter(
        OutreachSequenceStep.sequence_id == seq_id
    ).order_by(OutreachSequenceStep.step_order).all()

    if seq.current_step >= len(steps):
        seq.active = False
        seq.completed_at = datetime.utcnow()
        db.commit()
        return {"message": "Sequence already completed", "completed": True}

    step = steps[seq.current_step]
    lead = db.query(Lead).filter(Lead.id == seq.lead_id).first()

    if step.action_type in ("email", "linkedin", "call"):
        variables = {
            "business_name": lead.business_name if lead else "",
            "contact_name": lead.name if lead else "",
            "city": lead.city if lead else "",
            "niche": lead.niche if lead else "",
            "flaws": lead.flaws if lead else "Online presence issues detected",
            "score": str(lead.online_presence_score or 0),
            "website": lead.website_url or "",
            "phone": lead.phone or "",
            "my_name": "Your Name",
            "my_company": "Your Company",
        }

        subject, body = render_template(
            step.body or "", step.subject or "", variables
        )

        if step.action_type == "email" and lead and lead.email:
            result = await_email_send(lead.email, subject, body)
            step.notes = str(result)

        step.status = "sent"
        step.sent_at = datetime.utcnow()

        if lead:
            lead.outreach_message = body
            if lead.status == "new":
                lead.status = "contacted"
                lead.contacted_at = datetime.utcnow()

    seq.current_step += 1
    if seq.current_step >= len(steps):
        seq.active = False
        seq.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(seq)
    return {
        "message": f"Advanced to step {seq.current_step}/{len(steps)}",
        "completed": not seq.active,
        "step": step.step_order,
        "action_type": step.action_type,
    }


def await_email_send(to_email: str, subject: str, body: str):
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_email(to_email, subject, body))
        loop.close()
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/send-email/{lead_id}")
async def send_lead_email(lead_id: int, subject: str = Query(...), body: str = Query(...), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    variables = {
        "business_name": lead.business_name,
        "contact_name": lead.name,
        "city": lead.city or "",
        "niche": lead.niche or "",
        "flaws": lead.flaws or "",
        "score": str(lead.online_presence_score or 0),
        "website": lead.website_url or "",
        "phone": lead.phone or "",
        "my_name": "Your Name",
        "my_company": "Your Company",
    }
    final_subject, final_body = render_template(subject, body, variables)

    result = await send_email(lead.email, final_subject, final_body)

    if result.get("success"):
        lead.outreach_message = final_body
        if lead.status == "new":
            lead.status = "contacted"
            lead.contacted_at = datetime.utcnow()
        db.commit()

    return result


@router.post("/sequences/{seq_id}/pause")
def pause_sequence(seq_id: int, db: Session = Depends(get_db)):
    seq = db.query(OutreachSequence).filter(OutreachSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.active = False
    db.commit()
    return {"message": "Sequence paused"}


@router.post("/sequences/{seq_id}/resume")
def resume_sequence(seq_id: int, db: Session = Depends(get_db)):
    seq = db.query(OutreachSequence).filter(OutreachSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.active = True
    db.commit()
    return {"message": "Sequence resumed"}
