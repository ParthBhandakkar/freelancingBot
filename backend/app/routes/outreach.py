import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Lead, LeadAnalysis, OutreachTemplate, OutreachSequence, OutreachSequenceStep
from ..schemas import (
    OutreachTemplateCreate, OutreachTemplateUpdate, OutreachTemplateOut,
    OutreachSequenceCreate, OutreachSequenceOut,
)
from ..services.email_service import render_template, send_email
from ..services.settings_service import get_sender_identity, get_setting
from ..services.ai_service import draft_outreach, is_ai_available

logger = logging.getLogger(__name__)

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
    "audit_link": "Link to the generated audit report (if any)",
    "my_name": "Your name (Settings page)",
    "my_company": "Your company name (Settings page)",
    "my_website": "Your portfolio URL (Settings page)",
    "calendly_link": "Your booking link (Settings page)",
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
        "name": "Initial Outreach - Free Audit Attached",
        "description": "First contact with the generated audit report link (highest conversion)",
        "subject": "I made a free website review for {{business_name}}",
        "body": "Hi {{contact_name}},\n\nI put together a short review of {{business_name}}'s online presence — what's working, what's costing you customers, and what I'd fix first:\n\n{{audit_link}}\n\nIt took me a few minutes and it's yours either way. If it's useful, happy to walk you through it on a quick call.\n\nBest,\n{{my_name}}",
        "variables": ["business_name", "contact_name", "audit_link", "my_name"],
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
        "name": "Instagram/Facebook DM",
        "description": "Short DM for leads with no website but active social profiles",
        "subject": "DM",
        "body": "Hi! I came across {{business_name}} and love what you're doing. Noticed you don't have a website yet — I build simple, affordable sites for {{niche}} businesses in {{city}} that turn followers into customers. Want me to send over a quick example of what yours could look like? - {{my_name}}",
        "variables": ["business_name", "niche", "city", "my_name"],
        "channel": "dm",
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


def build_variables(lead: Lead, db: Session) -> dict:
    """Everything templates can reference — lead facts + sender identity from Settings."""
    sender = get_sender_identity(db)
    audit_link = ""
    if lead.asset_url:
        audit_link = lead.asset_url
    return {
        "business_name": lead.business_name or "",
        "contact_name": lead.name or "there",
        "city": lead.city or "",
        "niche": lead.niche or "local",
        "flaws": lead.flaws or "a few gaps in your online presence",
        "score": str(lead.online_presence_score or 0),
        "website": lead.website_url or "",
        "phone": lead.phone or "",
        "audit_link": audit_link,
        "my_name": sender["my_name"],
        "my_company": sender["my_company"],
        "my_website": sender["my_website"],
        "calendly_link": sender["calendly_link"],
    }


# ---------------------------------------------------------------- templates

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
    existing = {t.name for t in db.query(OutreachTemplate).all()}
    added = 0
    for tmpl in DEFAULT_TEMPLATES:
        if tmpl["name"] not in existing:
            db.add(OutreachTemplate(**tmpl))
            added += 1
    db.commit()
    return {"message": f"Seeded {added} new template(s)" if added else "All default templates already exist"}


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


# ---------------------------------------------------------------- AI drafting

@router.post("/draft/{lead_id}")
async def draft_message(lead_id: int, channel: str = Query("email"), db: Session = Depends(get_db)):
    """Draft a personalized message for this lead. Uses Claude when configured,
    otherwise falls back to the best matching template."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    analysis = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead_id).first()
    sender = get_sender_identity(db)

    draft = await draft_outreach(lead, analysis, sender, channel=channel)
    if draft:
        # Append the audit link if one exists and the model didn't include it
        if lead.asset_url and lead.asset_url not in draft["body"]:
            draft["body"] += f"\n\nP.S. I put together a free review of your online presence: {lead.asset_url}"
        return draft

    # Template fallback
    variables = build_variables(lead, db)
    tmpl = (
        db.query(OutreachTemplate)
        .filter(OutreachTemplate.channel == channel)
        .order_by(OutreachTemplate.id)
        .first()
    )
    if not tmpl:
        seed_default_templates(db)
        tmpl = db.query(OutreachTemplate).filter(OutreachTemplate.channel == channel).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"No template found for channel '{channel}'")

    subject, body = render_template(tmpl.body, tmpl.subject, variables)
    return {"subject": subject, "body": body, "ai": False}


@router.get("/ai-status")
def ai_status():
    return {"available": is_ai_available()}


# ---------------------------------------------------------------- sending

@router.post("/send-email/{lead_id}")
async def send_lead_email(lead_id: int, subject: str = Query(...), body: str = Query(...), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    variables = build_variables(lead, db)
    final_subject, final_body = render_template(subject, body, variables)

    signature = get_setting(db, "email_signature")
    if signature and signature not in final_body:
        final_body = final_body.rstrip() + "\n\n" + signature

    result = await send_email(lead.email, final_subject, final_body)

    if result.get("success"):
        lead.outreach_message = final_body
        if lead.status == "new":
            lead.status = "contacted"
            lead.contacted_at = datetime.utcnow()
        db.commit()
        logger.info("Sent email to lead #%s (%s)", lead.id, lead.email)

    return result


@router.post("/log-touch/{lead_id}")
def log_touch(lead_id: int, channel: str = Query("call"), note: str = Query(""), db: Session = Depends(get_db)):
    """One-click logging for calls and DMs made outside the app."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.status == "new":
        lead.status = "contacted"
    lead.contacted_at = datetime.utcnow()
    if note:
        lead.analysis_notes = ((lead.analysis_notes or "") + f"\n[{datetime.utcnow():%Y-%m-%d}] {channel}: {note}").strip()
    db.commit()
    return {"message": f"Logged {channel} touch", "lead_id": lead.id}


# ---------------------------------------------------------------- sequences

@router.get("/sequences", response_model=list[OutreachSequenceOut])
def list_sequences(lead_id: Optional[int] = None, active: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(OutreachSequence)
    if lead_id:
        query = query.filter(OutreachSequence.lead_id == lead_id)
    if active is not None:
        query = query.filter(OutreachSequence.active == active)
    return query.all()


@router.get("/sequences/due")
def list_due_sequences(db: Session = Depends(get_db)):
    """Sequence steps whose delay has elapsed — the follow-up queue."""
    due = get_due_steps(db)
    out = []
    for seq, step, lead in due:
        out.append({
            "sequence_id": seq.id,
            "sequence_name": seq.name,
            "step_id": step.id,
            "step_order": step.step_order,
            "action_type": step.action_type,
            "subject": step.subject,
            "lead_id": lead.id,
            "business_name": lead.business_name,
            "lead_email": lead.email,
            "lead_channel": lead.channel,
        })
    return {"total": len(out), "due": out}


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

    seq = OutreachSequence(lead_id=data.lead_id, name=data.name)
    db.add(seq)
    db.commit()
    db.refresh(seq)

    for step_data in data.steps:
        db.add(OutreachSequenceStep(
            sequence_id=seq.id,
            step_order=step_data.step_order,
            action_type=step_data.action_type,
            subject=step_data.subject,
            body=step_data.body,
            delay_days=step_data.delay_days,
        ))
    db.commit()
    db.refresh(seq)
    return seq


def get_due_steps(db: Session) -> list:
    """(sequence, step, lead) triples whose delay has elapsed and are ready to act on."""
    now = datetime.utcnow()
    due = []
    active_seqs = db.query(OutreachSequence).filter(OutreachSequence.active == True).all()
    for seq in active_seqs:
        steps = sorted(seq.steps, key=lambda s: s.step_order)
        if seq.current_step >= len(steps):
            continue
        step = steps[seq.current_step]
        if step.status != "pending":
            continue
        if seq.current_step == 0:
            reference = seq.started_at
        else:
            prev = steps[seq.current_step - 1]
            reference = prev.sent_at or seq.started_at
        if reference is None:
            reference = now
        # SQLite returns naive datetimes; normalize
        if getattr(reference, "tzinfo", None) is not None:
            reference = reference.replace(tzinfo=None)
        if now >= reference + timedelta(days=step.delay_days or 0):
            lead = db.query(Lead).filter(Lead.id == seq.lead_id).first()
            if lead and (lead.response or "pending") == "pending":
                due.append((seq, step, lead))
            elif lead:
                # Lead already responded/converted/rejected — stop the sequence
                seq.active = False
                seq.completed_at = now
                db.commit()
    return due


async def execute_step(seq: OutreachSequence, step: OutreachSequenceStep, lead: Lead, db: Session) -> dict:
    """Render and (for email) send one sequence step, then advance the sequence."""
    variables = build_variables(lead, db)
    subject, body = render_template(step.body or "", step.subject or "", variables)

    result = {"sent": False, "action_type": step.action_type}
    if step.action_type == "email" and lead.email:
        send_result = await send_email(lead.email, subject, body)
        step.notes = str(send_result)
        result["sent"] = bool(send_result.get("success"))
        result["detail"] = send_result
    else:
        # Calls / DMs / emails-without-address surface in the Today queue instead
        step.notes = "Marked done (manual channel or missing email)"

    step.status = "sent"
    step.sent_at = datetime.utcnow()

    if lead.status == "new":
        lead.status = "contacted"
        lead.contacted_at = datetime.utcnow()
    lead.outreach_message = body

    seq.current_step += 1
    steps_total = db.query(OutreachSequenceStep).filter(OutreachSequenceStep.sequence_id == seq.id).count()
    if seq.current_step >= steps_total:
        seq.active = False
        seq.completed_at = datetime.utcnow()

    db.commit()
    return result


@router.post("/sequences/{seq_id}/advance")
async def advance_sequence(seq_id: int, db: Session = Depends(get_db)):
    seq = db.query(OutreachSequence).filter(OutreachSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    steps = sorted(seq.steps, key=lambda s: s.step_order)
    if seq.current_step >= len(steps):
        seq.active = False
        seq.completed_at = datetime.utcnow()
        db.commit()
        return {"message": "Sequence already completed", "completed": True}

    step = steps[seq.current_step]
    lead = db.query(Lead).filter(Lead.id == seq.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await execute_step(seq, step, lead, db)
    db.refresh(seq)
    return {
        "message": f"Advanced to step {seq.current_step}/{len(steps)}",
        "completed": not seq.active,
        "step": step.step_order,
        "action_type": step.action_type,
        "sent": result.get("sent"),
    }


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
