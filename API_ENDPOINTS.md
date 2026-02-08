# DaVinci AI Backend - API Endpoints Reference

## Base URL
```
http://127.0.0.1:8000
```

## Interactive Documentation
- **Swagger UI**: http://127.0.0.1:8000/api/docs
- **ReDoc**: http://127.0.0.1:8000/api/redoc

---

## 🔐 Authentication Endpoints

### Register New Tenant
```http
POST /api/auth/register
Content-Type: application/json

{
  "organization_name": "Acme Corp",
  "email": "admin@acme.com",
  "password": "secure_password",
  "full_name": "John Doe"
}
```

**Response**: JWT token + user + tenant data

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin@davinciai.eu",
  "password": "password"
}
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@davinciai.eu",
    "full_name": "Demo Admin",
    "role": "admin"
  },
  "tenant": {
    "tenant_id": "demo-tenant-001",
    "organization_name": "Demo Corporation",
    "subdomain": "demo"
  }
}
```

### Get Current User
```http
GET /api/auth/me
Authorization: Bearer {token}
```

---

## 🏢 Tenant Endpoints

### Get Tenant Info
```http
GET /api/tenants/{tenant_id}
```

**Response**:
```json
{
  "tenant_id": "demo-tenant-001",
  "organization_name": "Demo Corporation",
  "subdomain": "demo",
  "plan_tier": "enterprise",
  "is_active": true,
  "created_at": "2026-01-28T10:00:00Z"
}
```

### List Tenant Agents
```http
GET /api/tenants/{tenant_id}/agents
```

**Response**:
```json
[
  {
    "agent_id": "tara-voice-001",
    "agent_name": "Tara",
    "agent_description": "Enterprise AI voice agent powered by Cartesia Sonic-3",
    "is_active": true,
    "stats": {
      "total_calls": 216,
      "total_minutes": 955,
      "success_rate": 0.927
    }
  }
]
```

---

## 🎤 Agent Endpoints

### Get Agent Details
```http
GET /api/agents/{agent_id}
```

**Response**:
```json
{
  "agent_id": "tara-support-001",
  "agent_name": "Tara - Customer Support",
  "cartesia_agent_id": "agent_demo_tara",
  "is_active": true,
  "configuration": {
    "system_prompt": "You are Tara, a customer support agent...",
    "voice_id": "248be419-c632-4f23-adf1-5324ed7dbf1d",
    "model": "llama-3.1-8b-instant"
  }
}
```

---

## 📊 Metrics & Analytics Endpoints

### Get Call Logs
```http
GET /api/metrics/calls?agent_id={agent_id}&limit=20
```

**Response**:
```json
[
  {
    "call_id": "call-1234",
    "duration_display": "11:22",
    "cost_euros": 5.0,
    "status": "completed",
    "start_time": "2026-01-29T14:23:00Z",
    "sentiment_score": 0.87
  }
]
```

### Get Analytics Dashboard
```http
GET /api/metrics/analytics?agent_id={agent_id}
```

**Response**:
```json
{
  "total_calls_today": 23,
  "total_minutes_today": 127,
  "total_cost_today": 8.40,
  "success_rate": 0.942,
  "avg_call_duration": 332,
  "active_calls": 3,
  "call_volume_trend": [
    {"hour": "00:00", "calls": 2},
    {"hour": "02:00", "calls": 1}
  ],
  "cost_breakdown": {
    "0-5_min": {"calls": 89, "cost": 178.00},
    "5-10_min": {"calls": 34, "cost": 119.00}
  }
}
```

### Get Real-time Active Calls
```http
GET /api/metrics/realtime?agent_id={agent_id}
```

**Response**:
```json
[
  {
    "call_id": "live-call-1",
    "duration_seconds": 145,
    "estimated_cost": 1.93,
    "status": "agent_speaking",
    "sentiment": "positive"
  }
]
```

---

## 💰 Wallet & Billing Endpoints

### Get Wallet Balance
```http
GET /api/wallet/{tenant_id}
```

**Response**:
```json
{
  "balance_euros": 45.50,
  "currency": "EUR",
  "estimated_calls_remaining": 10,
  "balance_status": "healthy"
}
```

### Get Transaction History
```http
GET /api/wallet/{tenant_id}/transactions?limit=20
```

**Response**:
```json
[
  {
    "transaction_id": "txn-001",
    "type": "topup",
    "amount_euros": 50.00,
    "description": "Top-up via Stripe",
    "created_at": "2026-01-27T10:00:00Z"
  },
  {
    "transaction_id": "txn-002",
    "type": "deduction",
    "amount_euros": -2.00,
    "description": "Call #1234 (3:45 min)",
    "created_at": "2026-01-28T09:15:00Z"
  }
]
```

### Initiate Top-up
```http
POST /api/wallet/{tenant_id}/topup
Content-Type: application/json

{
  "amount_euros": 50.00
}
```

**Response**:
```json
{
  "status": "initiated",
  "amount_euros": 50.00,
  "payment_intent_id": "pi_mock123456",
  "client_secret": "pi_mock123456_secret",
  "next_action": "Complete payment on frontend with Stripe Elements"
}
```

### Get Pricing Tiers
```http
GET /api/wallet/pricing/display
```

**Response**:
```json
{
  "tiers": [
    {"range": "0-5 min", "cost_euros": 2.00},
    {"range": "5-10 min", "cost_euros": 3.50},
    {"range": "10-15 min", "cost_euros": 5.00},
    {"range": "15+ min", "cost_euros": 7.00}
  ],
  "topup_presets": [10, 20, 50, 100]
}
```

---

## 🔔 Webhook Endpoints

### Cartesia Webhook Handler
```http
POST /webhooks/cartesia/{agent_id}
Content-Type: application/json

{
  "type": "call_completed",
  "request_id": "req_abc123",
  "body": [
    {
      "start_timestamp": 1706529600,
      "end_timestamp": 1706529900
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Webhook call_completed processed"
}
```

**Supported Event Types**:
- `call_started`: Call initiated
- `call_completed`: Call finished (triggers billing)
- `call_failed`: Call failed (no charge)

---

## 🏥 System Endpoints

### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "davinciai-backend"
}
```

### API Root
```http
GET /
```

**Response**:
```json
{
  "message": "DaVinci AI Backend API",
  "version": "1.0.0",
  "docs": "/api/docs"
}
```

---

## 🔑 Authentication Flow

1. **User logs in** → `POST /api/auth/login`
2. **Receive JWT token** + tenant_id
3. **Fetch agent** → `GET /api/tenants/{tenant_id}/agents`
4. **Redirect to dashboard** → `/enterprise/dashboard/{agent_id}`
5. **Load metrics** → `GET /api/metrics/analytics?agent_id={agent_id}`

---

## 📝 Notes

- All endpoints currently use **mock data** for prototype testing
- JWT tokens expire after 24 hours (configurable in `.env`)
- CORS is enabled for all origins in development mode
- Production deployment will require:
  - PostgreSQL database integration
  - Real Stripe payment processing
  - Webhook signature verification
  - Rate limiting and authentication middleware
