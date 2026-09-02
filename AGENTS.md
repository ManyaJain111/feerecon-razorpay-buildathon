# AGENTS.md

## What this is
Python CLI + FastAPI web app that audits payment-gateway fee contracts. LLM is
used **only** in `src/rule_extractor.py` (contract text → structured rules);
all fee arithmetic in `src/engine.py` is pure deterministic code.

## Quickstart
```bash
pip install -r requirements.txt        # pandas, pytest, tabulate, rich only - no LLM SDK
python3 run.py --extract --eval        # full pipeline: extract rules (3-pass) → reconcile → eval
python3 run.py --ui                    # FastAPI dashboard on http://localhost:8000
python3 -m pytest -v                   # 24 tests across 14 modules
python3 run.py --benchmark             # high-volume parallel scaling benchmark
```

## Entrypoints
- `run.py` - CLI orchestrator (see `main()` at run.py:41 for full flag list)
- `server.py` - FastAPI web UI (`start_server(8000)` from run.py:175)
- `eval/evaluate.py` - precision/recall/F1/throughput against `data/ground_truth.json`

## Architecture (worth knowing)
- **LLM scope**: only `src/rule_extractor.py` may call an LLM. Without
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` it falls back to a deterministic
  offline parser (still 100% reproducible).
- **Adapter factory**: `src/adapters/__init__.py:get_gateway_adapter(name)` →
  registered adapters: `razorpay`, `stripe`, `payu`. New gateway = subclass
  `src/adapters/base.py:GatewayAdapter` and add to the `ADAPTERS` dict.
- **Versioned rules**: `src/rules_registry.py` stores rules under
  `data/rules/rules_v{N}_{YYYY-MM-DD}.json`. Use `--rules-version 1.0` to pin.
- **Audit store**: `reports/audit_store.db` (SQLite, gitignored). Idempotency
  keys are derived from `(txn_id, batch_id, rule_version)`.

## CLI flags worth knowing
- `--extract` re-runs rule extraction. It runs extraction **3 times** and aborts
  if the runs disagree (logged to `reports/disagreements.json`). Use `--force`
  to proceed.
- `--update-dispute TXN_ID --dispute-status resolved --resolution-amount X`
  updates recovery tracking without re-running reconciliation.
- `--pdf path/to.pdf` classifies + extracts from a single PDF (contract vs.
  statement auto-detected by `src/pdf_processor.py`).
- `--generate-statements` regenerates CSVs and rules JSON for the 4 sample PDFs.

## Sample PDFs (multi-domain demos)
`sample_pdf/1.pdf` ... `4.pdf` are pre-paired with rule + statement files in
`data/`:
- `data/rules_1_axos.json` + `data/statement_1_axos.csv` (Wealth Advisory)
- `data/rules_2_sfusd.json` + `data/statement_2_sfusd.csv` (Public SaaS)
- `data/rules_3_huntington.json` + `data/statement_3_huntington.csv` (ETF Custody)
- `data/rules_4_btpanorama.json` + `data/statement_4_btpanorama.csv` (Brokerage)

The web UI's `/api/sample-pdfs` endpoint surfaces these as a loadable catalog.

## Severity tiers
Configured in `config/severity_thresholds.yaml`:
`CRITICAL` ≥ ₹1000 or ≥ 5%, `MODERATE` ≥ ₹100 or ≥ 1%, `MINOR` otherwise.
Confidence bands: high ≥ 0.95, medium ≥ 0.85.

## Adding a new gateway
1. Subclass `src/adapters/base.py:GatewayAdapter` - implement
   `gateway_name`, `parse_contract`, `parse_settlement`, `normalize_payment_method`.
2. Register the class in `src/adapters/__init__.py` `ADAPTERS` dict.
3. `python3 run.py --gateway <name> --settlement data/<file>.csv --extract`.

## Generated artifacts (all gitignored)
`reports/audit_trail.csv`, `reports/audit_store.db`,
`reports/dispute_draft_{BATCH}.md`, `reports/run_manifest_{ts}.json`,
`reports/disagreements.json`, `__pycache__/`.
