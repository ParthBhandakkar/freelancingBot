from pydantic import BaseModel
from typing import Optional
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
    niche: Optional[str] = None
    followers: Optional[int] = 0
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
    niche: Optional[str] = None
    followers: Optional[int] = 0
    online_presence_score: Optional[int] = 0
    flaws: Optional[str] = None
    analysis_notes: Optional[str] = None
    status: Optional[str] = "new"
    asset_generated: Optional[bool] = False
    asset_url: Optional[str] = None
    outreach_message: Optional[str] = None
    response: Optional[str] = "pending"
    contacted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
