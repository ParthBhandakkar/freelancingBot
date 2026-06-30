from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.sql import func
from .database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    profile_url = Column(String(500))
    website_url = Column(String(500))
    email = Column(String(255))
    phone = Column(String(50))
    city = Column(String(255))
    niche = Column(String(255))
    followers = Column(Integer, default=0)
    online_presence_score = Column(Integer, default=0)
    flaws = Column(Text)
    analysis_notes = Column(Text)
    status = Column(String(50), default="new")
    asset_generated = Column(Boolean, default=False)
    asset_url = Column(String(500))
    outreach_message = Column(Text)
    contacted_at = Column(DateTime, nullable=True)
    response = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
