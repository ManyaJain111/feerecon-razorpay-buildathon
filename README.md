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

```
Contract (PDF/Markdown)
       │
       ▼
┌──────────────────┐     ┌────────────────────────────────────┐
│ LLM Rule         │────▶│ Versioned Rules Registry           │
│ Extractor        │     │ (time-effective rulesets)          │
└──────────────────┘     └──────────────┬─────────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Gateway Adapters    │    │ Deterministic Fee   │    │ SQLite Audit Store  │
│ (Razorpay/Stripe/   │    │ Engine              │    │ - Idempotency keys  │
│  PayU/Custom)       │    │ - Parallel batches  │    │ - Dispute tracking  │
│ - parse_contract()  │    │ - Volume tiers      │    │ - Recovery KPIs     │
│ - parse_settlement()│    │ - Cap enforcement   │    └──────────┬──────────┘
│ - normalize_pm()    │    │ - Refund waivers    │               │
└─────────────────────┘    │ - GST calculation   │               ▼
         │                 └─────────────────────┘    ┌─────────────────────┐
         │                              │             │ Dispute Generator   │
         └──────────────────────────────┼────────────▶│ - Contract citations│
                                        │             │ - Itemized schedule │
                                        ▼             │ - Markdown draft    │
                           ┌─────────────────────┐    └─────────────────────┘
                           │ Transaction         │               │
                           │ Classifier          │               ▼
                           │ (MATCH/LEAK/        │    ┌─────────────────────┐
                           │  EXCEPTION/UNDER)   │    │ Trend Analyzer      │
                           │ - Severity tiers    │    │ - Recurring patterns│
                           │ - Confidence scores │    │ - Actionable alerts │
                           └─────────────────────┘    └─────────────────────┘
                                        │
                                        ▼
                           ┌─────────────────────────────────────┐
                           │ Run Manifest (Immutable)            │
                           │ Git commit | File SHA256 | Timestamp│
                           └─────────────────────────────────────┘
                                        │
                                        ▼
                           ┌─────────────────────────────────────┐
                           │ Financial Audit Report & Web UI     │
                           └─────────────────────────────────────┘
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

## Quickstart

### 1. Installation

```bash
git clone <repository-url>
cd razorpay-fee-leakage-detector
pip install -r requirements.txt
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
```

### 3. Launch Web UI Dashboard

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

## CLI Reference

| Flag | Description |
|------|-------------|
| `--gateway` | Payment gateway adapter: `razorpay`, `stripe`, `payu` (default: razorpay) |
| `--contract` | Path to merchant pricing contract (Markdown, plain text, or PDF) |
| `--settlement` | Path to settlement CSV or PDF file |
| `--pdf` | Process a single PDF contract or statement directly |
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

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Enables LLM-based extraction (Claude 3.5 Sonnet) |
| `OPENAI_API_KEY` | Alternative LLM provider (if configured) |

*Without API keys: Uses deterministic offline parser (100% reproducible)*

---

## Project Structure

```
.
├── run.py                      # Primary CLI orchestrator
├── server.py                   # FastAPI Web UI server
├── requirements.txt            # Project dependencies
├── .gitignore
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