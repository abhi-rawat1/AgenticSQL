# CustomerSupportAssist

CustomerSupportAssist is a production-style e-commerce support agent built for order lookup, customer service operations, inventory checks, return/refund governance, and semantic metric reporting.

This version now includes:

- realistic e-commerce seed data generation for 1,000–10,000-row scenarios
- proper return/refund approval statuses
- richer chart-based dashboard analytics
- separate dev/prod environment configuration
- local deployment instructions with Docker support

## Core capabilities

- Order lookup and order status tracking
- Customer and order history review
- Inventory health checks
- Return initiation and approval workflow
- Refund status and governance
- Semantic metrics like revenue, returns, and inventory risk
- Evidence-based audit logging and tracing

## Architecture overview

- SQL Query Builder & Executor
- Guardrails & policy validation
- Workflow orchestration for customer service actions
- Approval gateway for high-risk actions
- PostgreSQL-backed e-commerce dataset
- Streamlit analytics dashboard
- FastAPI approval API
- DBT-style semantic metric layer

## Recommended stack

- Python 3.11+
- PostgreSQL
- SQLAlchemy + psycopg
- LangChain + OpenAI-compatible LLM
- Streamlit
- FastAPI
- Docker Compose

## Folder structure

```text
customer_support_assist/
├── README.md
├── local_setup.md
├── architecture.md
├── requirements.txt
├── .env.example
├── .dev.env
├── .prod.env
├── app.py
├── api.py
├── settings.py
├── config.py
├── Dockerfile
├── docker-compose.yml
├── core/
│   ├── guardrails.py
│   └── tracing.py
├── services/
│   ├── approval_service.py
│   ├── db.py
│   ├── metrics_service.py
│   └── sql_agent.py
├── tools/
│   └── customer_support_tools.py
├── workflows/
│   └── support_workflow.py
├── scripts/
│   ├── load_ecommerce_data.py
│   └── generate_realistic_sales_data.py
├── sql/
│   ├── ecommerce_schema.sql
│   └── seed_ecommerce_large.sql
├── dbt/
│   └── semantic_models/
│       └── customer_support_metrics.yml
├── tests/
│   └── test_guardrails.py
├── logs/
│   └── support_audit.jsonl
└── approval_requests.jsonl
```

## Local setup

Follow the full setup instructions in [local_setup.md](local_setup.md).

### Run the JWT-backed app stack together

Start the API first:

```bash
cd customer_support_assist
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Then start the dashboard in a second terminal:

```bash
cd customer_support_assist
set CUSTOMER_SUPPORT_API_URL=http://localhost:8000
streamlit run app.py
```

Login using one of the seeded demo accounts:

- support_agent / support123
- ops_manager / ops123
- finance_analyst / finance123

The Streamlit app now logs in through the FastAPI `/login` endpoint and stores the JWT returned by the API. Protected approval and user-management actions are sent with the `Authorization: Bearer <token>` header.

## Dataset generation

To generate a more realistic sales dataset:

```bash
python scripts/generate_realistic_sales_data.py
```

This creates a large SQL seed file at:

- [customer_support_assist/sql/seed_ecommerce_large.sql](customer_support_assist/sql/seed_ecommerce_large.sql)

Then load it into PostgreSQL using:

```bash
python scripts/load_ecommerce_data.py
```

## Approval workflow statuses

Returns and refunds support these statuses:

- pending
- approved
- rejected
- cancelled

The approval API and dashboard both expose these statuses.

## Example support prompts

- Show order 10021 and shipping details
- Show customer 457 order history
- Check inventory for SKU-123
- What is the return rate for the last 30 days?
- Create a refund approval for order 10021

## Analytics on the dashboard

The dashboard includes charts for:

- revenue trend over time
- return volume trend
- inventory health trend
- support KPI snapshots

## Environment configuration

Use separate environment files for dev vs prod:

- [.dev.env](.dev.env)
- [.prod.env](.prod.env)

In production, set secure database, API, and model credentials separately from local development.

## Deployment

Run with Docker Compose:

```bash
docker-compose up --build
```

This exposes:

- Streamlit on port 8501
- FastAPI on port 8000

## Notes

This project remains isolated from the original SQL starter repository and is intentionally designed to evolve into a realistic customer support and ops assistant for e-commerce businesses.


## Architecture diagram

flowchart LR
    U[Support Agent / Operator] --> UI[Streamlit Dashboard\napp.py]
    U --> API[FastAPI Approval API\napi.py]

    UI --> WF[Support Workflow\nworkflows/support_workflow.py]
    API --> APS[Approval Service\nservices/approval_service.py]

    WF --> SA[SQL Agent\nservices/sql_agent.py]
    SA --> RG[Guardrails\ncore/guardrails.py]
    SA --> TOOLS[Support Tools\nlookup_order\nlookup_customer_orders\ncheck_inventory\nget_metric]

    TOOLS --> DB[(PostgreSQL E-commerce DB)]
    TOOLS --> MS[Metrics Service\nservices/metrics_service.py]
    MS --> DB

    RG --> TRACE[Audit & Trace Logs\ncore/tracing.py]
    APS --> APPROVAL_LOG[(Approval JSONL log)]
    TRACE --> LOGS[(Support Audit Logs)]

    DB --> RESP[Final Response]
    WF --> RESP
    APS --> RESP

    RESP --> UI
    RESP --> U