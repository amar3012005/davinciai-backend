from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum, Integer, Float, Numeric
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from .session import Base

class LoginMode(enum.Enum):
    DEMO = "demo"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_name = Column(String, nullable=False)
    subdomain = Column(String, nullable=False, unique=True)
    address = Column(Text, nullable=True)
    plan_tier = Column(String, default="enterprise")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    users = relationship("User", back_populates="tenant")

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    email = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin")
    login_mode = Column(Enum(LoginMode), default=LoginMode.DEMO, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Wallet(Base):
    __tablename__ = "wallets"

    wallet_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    balance = Column(Numeric(10, 2), default=0.0)
    currency = Column(String, default="EUR")
    is_auto_recharge_enabled = Column(Boolean, default=False)
    auto_recharge_amount = Column(Numeric(10, 2), default=0.0)
    low_balance_threshold = Column(Numeric(10, 2), default=10.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="wallets")
    agents = relationship("Agent", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet", order_by="Transaction.created_at.desc()")


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    wallet_id = Column(String, ForeignKey("wallets.wallet_id"), nullable=True) # Route billing to specific wallet
    
    # --- Identity & Branding ---
    agent_name = Column(String, nullable=False)
    agent_description = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True) # For UI visualization
    voice_sample_url = Column(String, nullable=True) # Audio preview
    location = Column(String, nullable=True)  # "Server Location" or "Persona Location"
    
    # --- Connectivity ---
    websocket_url = Column(String, nullable=True)
    phone_number = Column(String, nullable=True) # e.g., +14155550100
    sip_uri = Column(String, nullable=True) # e.g., sip:agent@voice.davinci.ai
    
    # --- Configuration ---
    language_primary = Column(String, default="en", nullable=False)
    language_secondary = Column(String, nullable=True)
    
    # Store complex configs as JSON
    # { "model": "gpt-4o", "temperature": 0.7, "system_prompt": "..." }
    llm_config = Column(Text, nullable=True) 
    
    # { "provider": "cartesia", "voice_id": "...", "speed": 1.0, "pitch": 0 }
    voice_config = Column(Text, nullable=True) 
    
    # { "first_sentence": "Hello...", "timeout_ms": 5000, "hangup_logic": "..." }
    flow_config = Column(Text, nullable=True)

    # --- Routing & Billing ---
    cartesia_agent_id = Column(String, nullable=True) # Legacy support
    configuration = Column(Text, nullable=True) # Legacy support
    cost_per_minute = Column(Numeric(10, 4), default=0.1500)
    routing_tier = Column(String, default="standard") # standard, premium, dedicated

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="agents")
    wallet = relationship("Wallet", back_populates="agents")
    calls = relationship("CallLog", back_populates="agent")


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    start_time = Column(DateTime(timezone=True), default=datetime.utcnow)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)
    status = Column(String, default="completed")  # completed, failed, interrupted
    caller_id = Column(String, nullable=True)
    ttft_ms = Column(Integer, nullable=True)
    ttfc_ms = Column(Integer, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    cost_euros = Column(Numeric(10, 4), default=0.0)

    agent = relationship("Agent", back_populates="calls")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String, ForeignKey("wallets.wallet_id"), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    type = Column(String, nullable=False)  # topup, deduction, refund
    amount_euros = Column(Numeric(10, 4), nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String, nullable=True)  # call_log id or stripe payment id
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    wallet = relationship("Wallet", back_populates="transactions")


# Update Tenant relations
Tenant.agents = relationship("Agent", back_populates="tenant")
Tenant.wallets = relationship("Wallet", back_populates="tenant")
