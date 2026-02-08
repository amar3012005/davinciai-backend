# DaVinci AI Backend

Multi-tenant voice agent monitoring platform with wallet-based billing.

## Quick Start (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Set up database
python scripts/init_db.py

# Run development server
uvicorn main:app --reload --port 8000
```

## Environment Variables

Create a `.env` file:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/davinciai
REDIS_URL=redis://localhost:6379

# Cartesia
CARTESIA_API_KEY=your_cartesia_api_key

# Security
JWT_SECRET=your_super_secret_key_change_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Frontend
FRONTEND_URL=http://localhost:3000
ALLOWED_ORIGINS=http://localhost:3000,https://dashboard.davinciai.eu

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Project Structure

```
davinciai-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration management
│   ├── database.py             # Database connection
│   ├── auth/                   # Authentication & authorization
│   │   ├── __init__.py
│   │   ├── router.py          # Auth routes (login, register)
│   │   ├── service.py         # Auth business logic
│   │   └── models.py          # User/Tenant models
│   ├── tenants/               # Tenant management
│   │   ├── __init__.py
│   │   ├── router.py          # Tenant CRUD routes
│   │   ├── service.py         # Tenant provisioning
│   │   └── models.py          # Tenant models
│   ├── agents/                # Agent management
│   │   ├── __init__.py
│   │   ├── router.py          # Agent routes
│   │   ├── service.py         # Agent provisioning
│   │   └── models.py          # Agent models
│   ├── metrics/               # Call metrics & analytics
│   │   ├── __init__.py
│   │   ├── router.py          # Metrics API
│   │   ├── service.py         # Aggregation logic
│   │   └── models.py          # CallLog, Metric models
│   ├── wallet/                # Billing & wallet
│   │   ├── __init__.py
│   │   ├── router.py          # Wallet routes
│   │   ├── service.py         # Billing engine
│   │   └── models.py          # Wallet, Transaction models
│   ├── webhooks/              # Cartesia webhook handlers
│   │   ├── __init__.py
│   │   └── cartesia.py        # Webhook processing
│   └── websockets/            # Real-time updates
│       ├── __init__.py
│       └── manager.py         # WebSocket connection manager
├── rules.py                   # Billing rules configuration
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new tenant
- `POST /api/auth/login` - Login user
- `POST /api/auth/refresh` - Refresh JWT token

### Tenants
- `GET /api/tenants/{tenant_id}` - Get tenant info
- `GET /api/tenants/{tenant_id}/agents` - List tenant's agents

### Agents
- `POST /api/tenants/{tenant_id}/agents` - Create new agent
- `GET /api/agents/{agent_id}` - Get agent details
- `GET /api/agents/{agent_id}/metrics` - Get agent metrics

### Metrics
- `GET /api/metrics/calls` - Get call logs (paginated)
- `GET /api/metrics/analytics` - Get aggregated analytics
- `GET /api/metrics/realtime` - Get live call data

### Wallet
- `GET /api/wallet/{tenant_id}` - Get wallet balance
- `POST /api/wallet/{tenant_id}/topup` - Initiate top-up
- `GET /api/wallet/{tenant_id}/transactions` - Transaction history

### Webhooks
- `POST /webhooks/cartesia/{agent_id}` - Cartesia event webhook

### WebSocket
- `WS /ws/{tenant_id}/{agent_id}` - Real-time updates

## Development

```bash
# Run tests
pytest

# Format code
black app/

# Lint
flake8 app/

# Type check
mypy app/
```

## Deployment (Hetzner)

See `deployment/README.md` for Docker deployment instructions.
