from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class LeadCreate(BaseModel):
    name: str
    business_name: str
    platform: str
    profile_url: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    niche: Optional[str] = None
    followers: Optional[int] = 0
    rating: Optional[float] = 0.0
    total_ratings: Optional[int] = 0
    source: Optional[str] = None
    flaws: Optional[str] = None
    analysis_notes: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    platform: Optional[str] = None
    profile_url: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    niche: Optional[str] = None
    followers: Optional[int] = None
    online_presence_score: Optional[int] = None
    flaws: Optional[str] = None
    analysis_notes: Optional[str] = None
    status: Optional[str] = None
    asset_generated: Optional[bool] = None
    asset_url: Optional[str] = None
    outreach_message: Optional[str] = None
    response: Optional[str] = None


class LeadOut(BaseModel):
    id: int
    name: str
    business_name: str
    platform: str
    profile_url: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    niche: Optional[str] = None
    followers: Optional[int] = 0
    rating: Optional[float] = 0.0
    total_ratings: Optional[int] = 0
    source: Optional[str] = None
    online_presence_score: Optional[int] = 0
    flaws: Optional[str] = None
    analysis_notes: Optional[str] = None
    status: Optional[str] = "new"
    asset_generated: Optional[bool] = False
    asset_url: Optional[str] = None
    outreach_message: Optional[str] = None
    response: Optional[str] = "pending"
    lead_score: Optional[int] = 0
    intent_signals: Optional[str] = None
    contacted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeadAnalysisCreate(BaseModel):
    lead_id: int


class LeadAnalysisOut(BaseModel):
    id: int
    lead_id: int
    tech_stack: Optional[Any] = None
    social_links: Optional[Any] = None
    review_snippets: Optional[list] = None
    business_hours: Optional[Any] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    social_metrics: Optional[Any] = None
    competitor_insights: Optional[Any] = None
    keyword_signals: Optional[list] = None
    analysis_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class OutreachTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    subject: str
    body: str
    variables: Optional[list] = None
    channel: Optional[str] = "email"


class OutreachTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[list] = None
    channel: Optional[str] = None


class OutreachTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    subject: str
    body: str
    variables: Optional[Any] = None
    channel: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OutreachSequenceStepCreate(BaseModel):
    step_order: int
    action_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    delay_days: int = 1


class OutreachSequenceStepOut(BaseModel):
    id: int
    sequence_id: int
    step_order: int
    action_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    delay_days: int
    status: str
    sent_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class OutreachSequenceCreate(BaseModel):
    lead_id: int
    name: str = "Default Sequence"
    steps: list[OutreachSequenceStepCreate]


class OutreachSequenceOut(BaseModel):
    id: int
    lead_id: int
    name: str
    active: bool
    current_step: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    steps: list[OutreachSequenceStepOut] = []

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_leads: int
    new_leads: int
    contacted: int
    responded: int
    converted: int
    assets_generated: int
    avg_presence_score: float
    leads_by_platform: dict
    leads_by_status: dict
    leads_by_city: list
