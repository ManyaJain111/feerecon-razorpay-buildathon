# Razorpay Fee Leakage Detector

An autonomous AI-powered gateway fee auditor that turns unstructured pricing contracts into structured rules, deterministically reconciles settlement transactions across multiple gateways, recovers billing leakage with 100% precision, and manages the full dispute lifecycle.

---

## The Problem

Enterprises processing high transaction volumes negotiate custom pricing contracts with payment gateways (Razorpay, Stripe, PayU). These contracts contain complex fee structures:

- **Tiered Volume MDR Discounts** - rates drop as cumulative monthly volume scales
- **Zero-MDR & Capped Instruments** - e.g., UPI at 0%, Netbanking capped at ₹20
- **Conditional Fee Waivers** - e.g., refund processing fee waived within 24 hours
- **Statutory GST (18%) Reconciliation**

**The Challenge:** Gateways routinely miscalculate volume tier cutoffs, bill default standard rates, or fail to apply conditional refund waivers. Because contracts live in unstructured PDFs while settlement reports contain thousands of raw CSV rows, **fee leakage of 0.5-2.5% silently goes undetected**.

---

## The Solution

An end-to-end reconciliation pipeline that uses an LLM **strictly for contract comprehension**, followed by a pure **deterministic calculation engine** that recomputes expected fees at **6,600+ transactions/second** with **zero arithmetic error**.

```mermaid
flowchart TD
    A[Contract (PDF/Markdown)] --> B[LLM Rule Extractor]
    B -->|confidence per rule + needs_review flags| C[Versioned Rules Registry]
    C -->|effective_from / effective_to windows<br/>status: verified \| unverified (conf<0.8)| D
    
    C --> D[Gateway Adapters<br/>Razorpay/Stripe/PayU/Custom<br/>parse_contract()<br/>parse_settlement()<br/>normalize_pm()]
    C --> E[Deterministic Fee Engine<br/>Parallel batches<br/>Volume tiers<br/>Cap enforcement<br/>Refund waivers<br/>GST calculation]
    C --> F[SQLite Audit Store (WAL)<br/>Single-writer by design<br/>Idempotency keys<br/>Dispute tracking + outcome: pending/accepted/rejected<br/>Recovery KPIs]
    
    D --> G[Transaction Classifier<br/>MATCH/LEAK/EXCEPTION/UNDERCHARGE<br/>Severity tiers<br/>match_confidence (not fee-arithmetic confidence)]
    E --> G
    F --> G
    
    G --> H[Dispute Generator<br/>Contract citations<br/>Itemized schedule<br/>Markdown draft]
    
    H --> I[Run Manifest (Immutable)<br/>Git commit \| contract_sha256 \| settlement_sha256 \| Timestamp]
    
    I --> J[Trend Analyzer<br/>Recurring patterns<br/>Actionable alerts]
    
    J --> K[Financial Audit Report & Web UI]
```

---

## Core Design Principle: Separation of LLM & Math

> **Zero LLM in the Arithmetic Loop**
>
> - **LLM Role (Cognitive):** Extracts pricing tables, tier brackets, caps, and waiver clauses from unstructured contract text into a validated `rules.json` schema with confidence scores, source spans, and `needs_review` flags.
> - **Deterministic Code Role (Financial Precision):** Recomputes expected MDR, applies volume tiers, enforces fee caps, waives conditional charges, calculates GST, and flags discrepancies.
> - **Self-Consistency Validation:** Multi-pass extraction with field-level diffing flags any extraction disagreements and auto-marks discordant rules for review.

*Financial controllers require zero hallucination and 100% repeatable math. We never let an LLM do financial arithmetic.*

---

## Architecture Details (from AGENTS.md)

### LLM Scope
Only `src/rule_extractor.py` may call an LLM. Without `NVIDIA_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` it falls back to a deterministic offline parser (still 100% reproducible).

### Adapter Factory
`src/adapters/__init__.py:get_gateway_adapter(name)` → registered adapters: `razorpay`, `stripe`, `payu`. New gateway = subclass `src/adapters/base.py:GatewayAdapter` and add to the `ADAPTERS` dict.

### Versioned Rules Registry
`src/rules_registry.py` stores rules under `data/rules/rules_v{N}_{YYYY-MM-DD}.json`. Use `--rules-version 1.0` to pin.

### Audit Store
`reports/audit_store.db` (SQLite, gitignored). Idempotency keys are derived from `(txn_id, batch_id, rule_version)`.

### Generated Artifacts (all gitignored)
- `reports/audit_trail.csv`
- `reports/audit_store.db`
- `reports/dispute_draft_{BATCH}.md`
- `reports/run_manifest_{ts}.json`
- `reports/disagreements.json`
- `__pycache__/`

---

## Benchmark Results

Tested on a synthetic settlement batch of **83 transactions** against `data/ground_truth.json`:

| Metric | Result | Target |
|--------|--------|--------|
| **Throughput** | 6,674 txns/sec (12.4 ms) | Sub-second latency |
| **Leak Detection Precision** | 100% (15/15 caught, 0 false alarms) | Zero false alarms |
| **Leak Detection Recall** | 100% (15/15 leaks identified) | Zero missed leaks |
| **F1-Score** | 100% | Optimal |
| **Exception Accuracy** | 100% (3/3 unresolvable clauses flagged) | Complete safety |
| **Financial Discrepancy Error** | ₹0.00 (0.00% error) | Exact ₹576.01 recovery |

---

## Quickstart (Local Dev)

### 1. Installation

```bash
git clone <repository-url>
cd razorpay-fee-leakage-detector
pip install -r requirements.txt        # pandas, pytest, tabulate, rich only - no LLM SDK
```

### 2. Run Full Reconciliation Pipeline

```bash
# Extract rules with self-consistency check (3 passes), reconcile, generate dispute, create manifest, run eval
python3 run.py --extract --eval

# Use a specific gateway adapter
python3 run.py --gateway stripe --settlement data/settlement_stripe.csv --extract

# Pin to a specific ruleset version from registry
python3 run.py --rules-version 1.0

# Force extraction despite consistency disagreements
python3 run.py --extract --force

# Update dispute tracking for a resolved claim
python3 run.py --update-dispute TXN_123 --dispute-status resolved --resolution-amount 576.01

# Process a single PDF (contract or statement, auto-detected)
python3 run.py --pdf sample_pdf/1.pdf

# Regenerate CSVs and rules JSON for the 4 sample PDFs
python3 run.py --generate-statements
```

### 3. Launch Web UI Dashboard (local)

```bash
python3 run.py --ui
# Available at http://localhost:8000
```

### 4. Run Test Suite

```bash
python3 -m pytest -v
```

### 5. High-Volume Benchmark

```bash
python3 run.py --benchmark
```

---

## Sample PDFs (Multi-Domain Demos)

`sample_pdf/1.pdf` ... `4.pdf` are pre-paired with rule + statement files in `data/`:

| PDF | Domain | Rules File | Statement File |
|-----|--------|------------|----------------|
| `sample_pdf/1.pdf` | Wealth Advisory | `data/rules_1_axos.json` | `data/statement_1_axos.csv` |
| `sample_pdf/2.pdf` | Public SaaS | `data/rules_2_sfusd.json` | `data/statement_2_sfusd.csv` |
| `sample_pdf/3.pdf` | ETF Custody | `data/rules_3_huntington.json` | `data/statement_3_huntington.csv` |
| `sample_pdf/4.pdf` | Brokerage | `data/rules_4_btpanorama.json` | `data/statement_4_btpanorama.csv` |

Load via web UI: `POST /api/load-sample` with `{"sample_id": "1"}` or CLI: `python3 run.py --pdf sample_pdf/1.pdf`

---

## Deploying to Azure App Service

The app runs as a native Python 3.11 app on Azure App Service (Linux).
CI/CD is handled by GitHub Actions (`.github/workflows/azure-deploy.yml`):
every push to `main` runs the test suite and, on success, deploys automatically.

### Prerequisites

- Azure CLI installed and logged in (`az login`)
- A GitHub repo with this code
- An Azure subscription

### Step 1 — Create the App Service

```bash
# Variables — change these to match your setup
RESOURCE_GROUP=rg-feerecon
APP_NAME=razorpay-fee-detector      # must be globally unique
LOCATION=eastus
PLAN_NAME=plan-feerecon

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan (B1 = ~$13/mo; use F1 for free tier)
az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku B1 \
  --is-linux

# Create the Web App with Python 3.11 runtime
az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --runtime "PYTHON:3.11"

# Set the startup script
# startup.sh runs: gunicorn -w 2 -k uvicorn.workers.UvicornWorker server:app
# (server.py exposes a module-level `app = create_app()` FastAPI instance)
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"
```

### Step 2 — Set Environment Variables (App Settings)

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    ANTHROPIC_API_KEY="<your-key-or-leave-blank>" \
    OPENAI_API_KEY="<your-key-or-leave-blank>" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

> **Note:** Without API keys the app uses the deterministic offline parser — fully functional with no LLM costs.

### Step 3 — Configure OIDC Federated Credentials for GitHub Actions

The workflow uses **OpenID Connect (OIDC)** — no long-lived secret JSON required.

```bash
# 1. Create the service principal (no --sdk-auth flag)
az ad sp create-for-rbac \
  --name "sp-feerecon-github" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/$RESOURCE_GROUP

# Note the output — you need appId (client ID) and tenant
```

```bash
# 2. Add a federated credential trusting your GitHub repo's main branch
az ad app federated-credential create \
  --id <appId-from-above> \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<YOUR_GITHUB_ORG>/<YOUR_REPO>:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

In your GitHub repo go to:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `AZURE_CLIENT_ID` | `appId` from the `az ad sp create-for-rbac` output |
| `AZURE_TENANT_ID` | `tenant` from the same output |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Resource group containing `razorpay-api-manya` |

### Step 4 — Trigger Deployment

Push to `main` (or go to **Actions → Deploy to Azure App Service → Run workflow**).

The pipeline will:
1. Run `pytest` — aborts deployment if any test fails
2. Login to Azure via OIDC (no stored credentials)
3. Set `startup.sh` as the App Service startup command
4. Zip-deploy source; Oryx installs `requirements.txt` server-side

### Step 5 — Verify

```bash
# Health check
curl https://$APP_NAME.azurewebsites.net/health

# Open in browser
az webapp browse --name $APP_NAME --resource-group $RESOURCE_GROUP
```

### Persistent Storage for Reports (optional but recommended)

Azure App Service has an ephemeral local filesystem. To persist audit reports across restarts, mount an Azure Files share:

```bash
# Create storage account
az storage account create \
  --name stfeerecon \
  --resource-group $RESOURCE_GROUP \
  --sku Standard_LRS

# Create file share
az storage share create --name reports --account-name stfeerecon

# Mount to /home/site/wwwroot/reports
az webapp config storage-account add \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --custom-id ReportsMount \
  --storage-type AzureFiles \
  --account-name stfeerecon \
  --share-name reports \
  --mount-path /home/site/wwwroot/reports \
  --access-key "$(az storage account keys list --account-name stfeerecon --query '[0].value' -o tsv)"
```

### Useful Azure CLI Commands

```bash
# Stream live logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# SSH into the app (Kudu console)
az webapp ssh --name $APP_NAME --resource-group $RESOURCE_GROUP

# Restart
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

# Scale up (e.g., to P2v3 for higher throughput)
az appservice plan update \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku P2v3
```

---

## CLI Reference

| Flag | Description |
|------|-------------|
| `--gateway` | Payment gateway adapter: `razorpay`, `stripe`, `payu` (default: razorpay) |
| `--contract` | Path to merchant pricing contract (Markdown, plain text, or PDF) |
| `--settlement` | Path to settlement CSV or PDF file |
| `--pdf` | Process a single PDF contract or statement directly (auto-detected) |
| `--extract` | Force re-extraction of rules with 3-pass consistency validation |
| `--force` | Proceed despite extraction disagreements |
| `--rules-version` | Pin to specific ruleset version (e.g., `1.0`) |
| `--generate-dispute` | Auto-generate dispute claim draft for detected leaks (default: true) |
| `--update-dispute` | Update dispute status for a transaction ID |
| `--dispute-status` | Status to apply: `none`, `submitted`, `acknowledged`, `resolved`, `rejected` |
| `--resolution-amount` | Recovered amount to record with dispute update |
| `--eval` | Run precision/recall benchmark against ground truth |
| `--benchmark` | Run high-volume parallel scaling benchmark |
| `--ui` | Launch FastAPI web dashboard |
| `--generate-statements` | Regenerate account statement CSVs for sample PDFs |

---

## Sample Audit Output

```
======================================================================
        RAZORPAY FEE LEAKAGE DETECTOR: AUDIT SUMMARY
======================================================================
Batch ID / Rule Version      : BATCH_A1B2C3D4 | v1.0
Total Transactions Processed : 83
Total GMV Volume Processed   : ₹713,846.00
Total Gateway Fees Billed    : ₹12,179.35
Total Expected Contract Fees : ₹10,989.74
TOTAL DETECTED FEE LEAKAGE   : ₹576.01
----------------------------------------------------------------------
Clean Matches                : 65 (78.31%)
Fee Leaks (Overcharges)      : 15 (18.07%)
Exceptions (Needs Review)    : 3 (3.61%)
----------------------------------------------------------------------
SEVERITY & MATERIALITY TIERS:
  • CRITICAL    :  2 txns | ₹  312.69
  • MODERATE    :  8 txns | ₹  175.82
  • MINOR       :  5 txns | ₹   87.50
----------------------------------------------------------------------
LEAKAGE BREAKDOWN BY TYPE:
  • UPI_NON_ZERO_MDR                :  2 txns | ₹    3.84
  • FEE_OVERCHARGE                  :  1 txns | ₹   35.40
  • WRONG_TIER_APPLIED              :  7 txns | ₹  277.29
  • CAP_VIOLATION                   :  2 txns | ₹  175.82
  • INTL_RATE_SURCHARGE_OVERCHARGE  :  2 txns | ₹   80.83
  • WALLET_OVERCHARGE               :  1 txns | ₹    2.83
----------------------------------------------------------------------
DISPUTE & RECOVERY STATUS:
  • Total Detected Leakage   : ₹576.01
  • Total Recovered Leakage  : ₹0.00 (0.00%)
  • Dispute Claims Resolved  : 0
----------------------------------------------------------------------
CROSS-RUN TREND ALERTS:
  • [HIGH] WRONG_TIER_APPLIED recurred across 3 batches (21 txns, ₹831.87)
    -> Systemic volume bracket mismatch - recommend contract renegotiation review.
----------------------------------------------------------------------
UNRESOLVED CONTRACT EXCEPTIONS:
  • [TXN_INSTANT_0003] DOMESTIC_CARD (₹20,000): Instant settlement with risk
    rating 'SPECIAL_REVIEW' requires manual offline authorization (Clause 3.1.b).
======================================================================
[OK] Detailed audit trail: reports/audit_trail.csv
[OK] Dispute claim draft: reports/dispute_draft_BATCH_A1B2C3D4.md
[OK] Run manifest: reports/run_manifest_20250825_143022.json
```

---

## Web UI Dashboard

Launch with `python3 run.py --ui` → `http://localhost:8000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Interactive dashboard with reconciliation summary |
| `/api/reconciliation` | GET | Full reconciliation JSON (summary + records + performance) |
| `/api/upload-settlement` | POST | Upload custom settlement CSV for ad-hoc reconciliation |
| `/api/contract` | GET | Raw contract + extracted rules JSON |
| `/api/dispute-draft` | GET | Latest auto-generated dispute claim markdown |
| `/api/export-audit` | GET | Download audit_trail.csv |
| `/api/load-sample` | POST | Load a sample PDF contract/statement pair |
| `/api/sample-pdfs` | GET | List available sample PDFs with metadata |
| `/api/download-statement/{id}` | GET | Download sample account statement CSV |
| `/api/process-pdf` | POST | Upload and process a PDF contract or statement |

---

## Extending for New Gateways

1. Create `src/adapters/<gateway>.py` implementing `GatewayAdapter`:

```python
from src.adapters.base import GatewayAdapter
from src.schema import PaymentMethodEnum

class NewGatewayAdapter(GatewayAdapter):
    @property
    def gateway_name(self) -> str:
        return "newgateway"

    def parse_contract(self, contract_path: str) -> Dict[str, Any]:
        # Extract rules using shared extractor or gateway-specific logic
        ...

    def parse_settlement(self, settlement_path: str, chunksize: int = 50_000) -> List[Dict[str, Any]]:
        # Parse gateway-specific CSV format into canonical schema
        ...

    def normalize_payment_method(self, raw_method: str) -> PaymentMethodEnum:
        # Map gateway strings to canonical enum
        return PaymentMethodEnum.normalize(raw_method)
```

2. Register in `src/adapters/__init__.py`:

```python
def get_gateway_adapter(name: str) -> GatewayAdapter:
    adapters = {
        "razorpay": RazorpayAdapter(),
        "stripe": StripeAdapter(),
        "payu": PayUAdapter(),
        "newgateway": NewGatewayAdapter()
    }
    return adapters[name.lower()]
```

3. Run: `python3 run.py --gateway newgateway --settlement data/settlement_newgateway.csv --extract`

---

## GST Scoping Note

> **GST logic covers CGST/SGST at a flat rate on service charges; IGST, HSN-code-dependent rates, and rate-change history are out of scope for this build.**

---

## Configuration

### Severity Thresholds (`config/severity_thresholds.yaml`)

```yaml
severity_thresholds:
  critical:
    min_amount: 1000.0
    min_percentage: 5.0
  moderate:
    min_amount: 100.0
    min_percentage: 1.0
  minor:
    min_amount: 0.0
    min_percentage: 0.0
confidence_thresholds:
  high: 0.95
  medium: 0.85
  low: 0.0
```

#### Environment Variables

| Variable | Purpose |
|----------|---------| 
| `NVIDIA_API_KEY` | **Primary** - Enables NVIDIA NIM models (Nemotron-3-Ultra, Llama-3.1-Nemotron-70B) for rule extraction |
| `ANTHROPIC_API_KEY` | Fallback LLM (Claude 3.5 Sonnet) |
| `OPENAI_API_KEY` | Alternative LLM provider |

*Without API keys: Uses deterministic offline parser (100% reproducible, no NVIDIA NIM features)*

**Local Development** - Create `.env` file in project root:
```bash
NVIDIA_API_KEY=your_nvidia_nim_key_here
# Optional fallbacks:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

**On Azure App Service**, set via portal (*Configuration → Application settings*) or CLI:
```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings NVIDIA_API_KEY="your_key" ANTHROPIC_API_KEY="sk-..." OPENAI_API_KEY="sk-..."
```

**NVIDIA NIM Models Used:**
- `nvidia/nemotron-3-ultra` - Primary rule extraction (best reasoning)
- `nvidia/llama-3.1-nemotron-70b-instruct` - Fast fallback
- `nvidia/llama-3.1-nemotron-51b` - Lightweight option

---

## Project Structure

```
.
├── run.py                      # Primary CLI orchestrator
├── server.py                   # FastAPI Web UI server
├── startup.sh                  # Azure App Service startup script
├── requirements.txt            # Project dependencies
├── .gitignore
├── .github/
│   └── workflows/
│       └── azure-deploy.yml    # GitHub Actions CI/CD → Azure App Service
├── config/
│   └── severity_thresholds.yaml
├── data/
│   ├── contract.md             # Synthetic multi-tier pricing contract
│   ├── generate_settlement.py  # Synthetic generator with seeded leaks
│   ├── settlement.csv          # 83 transaction settlement records
│   ├── ground_truth.json       # Ground truth leak & exception registry
│   └── rules/                  # Versioned rulesets (rules_v{N}_{date}.json)
├── src/
│   ├── __init__.py
│   ├── schema.py               # Canonical enums & Pydantic models
│   ├── rule_extractor.py       # Contract → rules.json (LLM + offline fallback)
│   ├── rule_validator.py       # Multi-run self-consistency checks
│   ├── rules_registry.py       # Versioned rule registry with time-effective lookup
│   ├── loader.py               # Ingestion, validation & type normalization
│   ├── engine.py               # Pure deterministic fee calculation engine
│   ├── classifier.py           # Discrepancy detector with severity/confidence
│   ├── report.py               # Reconciliation aggregator & CSV audit exporter
│   ├── audit_store.py          # SQLite audit trail + dispute tracking + KPIs
│   ├── dispute_generator.py    # Formal dispute claim draft generator
│   ├── trend_analyzer.py       # Cross-run recurring pattern detection
│   ├── manifest.py             # Immutable run manifest generation
│   ├── pdf_processor.py        # PDF ingestion & classification
│   └── adapters/
│       ├── __init__.py         # get_gateway_adapter() factory
│       ├── base.py             # GatewayAdapter abstract base class
│       ├── razorpay.py         # Razorpay implementation
│       ├── stripe.py           # Stripe implementation
│       └── payu.py             # PayU implementation
├── eval/
│   └── evaluate.py             # Precision/Recall/F1/Throughput benchmark suite
├── tests/                      # Pytest unit tests (14 test modules)
├── reports/                    # Generated outputs (gitignored)
├── static/                     # Web UI assets
└── docs/
    └── application_answers.md  # Hackathon form answers
```

---

## License

MIT License - see LICENSE file for details.