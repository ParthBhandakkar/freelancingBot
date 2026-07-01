from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    lead_score = Column(Integer, default=0)
    intent_signals = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    analyses = relationship("LeadAnalysis", back_populates="lead", cascade="all, delete-orphan")
    sequences = relationship("OutreachSequence", back_populates="lead", cascade="all, delete-orphan")


class LeadAnalysis(Base):
    __tablename__ = "lead_analyses"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    tech_stack = Column(JSON, default=dict)
    social_links = Column(JSON, default=dict)
    review_snippets = Column(JSON, default=list)
    business_hours = Column(JSON, default=dict)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    social_metrics = Column(JSON, default=dict)
    competitor_insights = Column(JSON, default=dict)
    keyword_signals = Column(JSON, default=list)
    analysis_date = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="analyses")


class OutreachTemplate(Base):
    __tablename__ = "outreach_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    channel = Column(String(50), default="email")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), default="Default Sequence")
    active = Column(Boolean, default=True)
    current_step = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    lead = relationship("Lead", back_populates="sequences")
    steps = relationship("OutreachSequenceStep", back_populates="sequence", cascade="all, delete-orphan", order_by="OutreachSequenceStep.step_order")


class OutreachSequenceStep(Base):
    __tablename__ = "outreach_sequence_steps"

    id = Column(Integer, primary_key=True, index=True)
    sequence_id = Column(Integer, ForeignKey("outreach_sequences.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    action_type = Column(String(50), nullable=False)
    subject = Column(String(500))
    body = Column(Text)
    delay_days = Column(Integer, default=1)
    status = Column(String(50), default="pending")
    sent_at = Column(DateTime, nullable=True)
    notes = Column(Text)

    sequence = relationship("OutreachSequence", back_populates="steps")
