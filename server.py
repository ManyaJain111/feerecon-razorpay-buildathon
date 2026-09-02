"""FastAPI and HTTP server for the fee reconciliation dashboard and API."""

import os
import io
import sys
import json
import time
import glob
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.loader import load_settlement_csv
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.report import ReconciliationReporter
from src.rule_extractor import extract_rules
from src.audit_store import AuditStore
from src.dispute_generator import generate_dispute_draft
from src.pdf_processor import (
    extract_text_from_pdf,
    detect_pdf_document_type,
    extract_rules_from_pdf_text,
    parse_statement_from_pdf_text
)

STATIC_DIR = BASE_DIR / "static"
CONTRACT_PATH = "data/contract.md"
SETTLEMENT_PATH = "data/settlement.csv"
RULES_PATH = "src/rules.json"

SAMPLE_PDF_CATALOG = [
    {
        "id": "1",
        "filename": "1.pdf",
        "title": "Axos Advisor Services Standard Fee Schedule",
        "category": "Wealth Advisory & Clearing",
        "description": "Standard pricing for advisory trading (equities, mutual funds, options), custody maintenance, domestic/intl wire transfers, and money movement.",
        "statement_file": "data/statement_1_axos.csv",
        "rules_file": "data/rules_1_axos.json",
        "sample_statement_path": "sample_pdf/1_account_statement.csv"
    },
    {
        "id": "2",
        "filename": "2.pdf",
        "title": "SFUSD & DreamBox Learning Master Agreement",
        "category": "Public Sector / Software SaaS",
        "description": "3-year hosted software services agreement covering district school site licenses (Tier 1/2), teacher PD webinars, and SIS integrations.",
        "statement_file": "data/statement_2_sfusd.csv",
        "rules_file": "data/rules_2_sfusd.json",
        "sample_statement_path": "sample_pdf/2_account_statement.csv"
    },
    {
        "id": "3",
        "filename": "3.pdf",
        "title": "Huntington Strategy Shares & Citibank Fee Schedule",
        "category": "Institutional ETF Custody & Administration",
        "description": "Asset-based administration tiers ($500M/$1B), Authorized Participant creation/redemption agency fees, and global custody settlement across 20+ countries.",
        "statement_file": "data/statement_3_huntington.csv",
        "rules_file": "data/rules_3_huntington.json",
        "sample_statement_path": "sample_pdf/3_account_statement.csv"
    },
    {
        "id": "4",
        "filename": "4.pdf",
        "title": "BT Panorama & eWRAP Investment Fee Schedule",
        "category": "Investment Platform & Brokerage",
        "description": "Account-based monthly administration, tiered asset fees, listed securities brokerage, managed fund transaction spreads, and net RITC adjustments.",
        "statement_file": "data/statement_4_btpanorama.csv",
        "rules_file": "data/rules_4_btpanorama.json",
        "sample_statement_path": "sample_pdf/4_account_statement.csv"
    }
]

def get_engine_and_rules(rules_override: Optional[Dict[str, Any]] = None):
    if rules_override:
        return FeeCalculationEngine(rules_override), rules_override
    if not os.path.exists(RULES_PATH):
        extract_rules(CONTRACT_PATH, output_path=RULES_PATH)
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules_data = json.load(f)
    engine = FeeCalculationEngine(rules_data)
    return engine, rules_data

def run_reconciliation(settlement_path_or_records, rules_override=None, batch_id="DEFAULT_BATCH"):
    engine, rules_data = get_engine_and_rules(rules_override)
    classifier = TransactionClassifier(engine)
    
    if isinstance(settlement_path_or_records, str):
        records = load_settlement_csv(settlement_path_or_records)
    else:
        records = settlement_path_or_records

    start_t = time.perf_counter()
    classified_records = classifier.classify_all(records)
    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

    reporter = ReconciliationReporter(classified_records, batch_id=batch_id)
    reporter.sync_to_audit_store()
    summary = reporter.compute_summary()
    reporter.export_audit_trail_csv("reports/audit_trail.csv")

    return {
        "summary": summary,
        "performance": {
            "elapsed_ms": elapsed_ms,
            "throughput_txns_sec": round(len(records) / (elapsed_ms / 1000.0), 1) if elapsed_ms > 0 else 0
        },
        "records": classified_records,
        "rules_used": rules_data
    }

def apply_policy_prompt(rules_data: Dict[str, Any], prompt: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse natural language policy prompt and apply changes to rules.
    Returns amended rules and list of applied changes.
    """
    import copy
    import re
    
    amended = copy.deepcopy(rules_data)
    changes = []
    prompt_lower = prompt.lower()
    
    # Netbanking fee cap changes
    cap_match = re.search(r'(?:cap|maximum).*?netbanking.*?(\d+(?:\.\d+)?)', prompt_lower)
    if not cap_match:
        cap_match = re.search(r'netbanking.*?(?:cap|maximum).*?(\d+(?:\.\d+)?)', prompt_lower)
    if not cap_match:
        cap_match = re.search(r'cap.*?(\d+(?:\.\d+)?).*?netbanking', prompt_lower)
    
    if cap_match:
        new_cap = float(cap_match.group(1))
        old_cap = amended["rules"]["payment_methods"]["NETBANKING"].get("fee_cap", 20.0)
        amended["rules"]["payment_methods"]["NETBANKING"]["fee_cap"] = new_cap
        changes.append(f"Netbanking fee cap: ₹{old_cap:.2f} → ₹{new_cap:.2f}")
    
    # Domestic Card rate changes (tiered -> flat)
    card_rate_match = re.search(r'(?:domestic\s+)?card.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if not card_rate_match:
        card_rate_match = re.search(r'(\d+(?:\.\d+)?)\s*%.*?card', prompt_lower)
    if not card_rate_match:
        card_rate_match = re.search(r'discount.*?card.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    
    if card_rate_match:
        new_rate = float(card_rate_match.group(1))
        old_tiers = amended["rules"]["payment_methods"]["DOMESTIC_CARD"]["tiers"]
        amended["rules"]["payment_methods"]["DOMESTIC_CARD"]["type"] = "flat"
        amended["rules"]["payment_methods"]["DOMESTIC_CARD"]["rate_pct"] = new_rate
        amended["rules"]["payment_methods"]["DOMESTIC_CARD"]["tiers"] = []
        changes.append(f"Domestic Card rate: tiered → flat {new_rate}%")
    
    # Refund fee waiver
    if "waive" in prompt_lower and ("refund" in prompt_lower or "late fine" in prompt_lower or "late fee" in prompt_lower):
        old_fee = amended["rules"]["refund_policy"].get("standard_fee", 5.0)
        amended["rules"]["refund_policy"]["standard_fee"] = 0.0
        amended["rules"]["refund_policy"]["waived_fee"] = 0.0
        changes.append(f"Refund/late fee: ₹{old_fee:.2f} → ₹0.00 (waived)")
    
    # Instant settlement surcharge waiver
    if "waive" in prompt_lower and "instant" in prompt_lower:
        old_rate = amended["rules"]["instant_settlement"].get("rate_pct", 0.15)
        amended["rules"]["instant_settlement"]["rate_pct"] = 0.0
        changes.append(f"Instant settlement surcharge: {old_rate}% → 0% (waived)")
    
    # UPI zero MDR enforcement (already 0%)
    if "upi" in prompt_lower and ("zero" in prompt_lower or "0%" in prompt_lower or "waive" in prompt_lower):
        if amended["rules"]["payment_methods"]["UPI"]["rate_pct"] != 0.0:
            amended["rules"]["payment_methods"]["UPI"]["rate_pct"] = 0.0
            amended["rules"]["payment_methods"]["UPI"]["fixed_fee"] = 0.0
            changes.append("UPI MDR enforced to 0% (Zero MDR)")
    
    # International card rate change
    intl_match = re.search(r'international.*?card.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if not intl_match:
        intl_match = re.search(r'intl.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if intl_match:
        new_rate = float(intl_match.group(1))
        old_rate = amended["rules"]["payment_methods"]["INTERNATIONAL_CARD"].get("rate_pct", 3.0)
        amended["rules"]["payment_methods"]["INTERNATIONAL_CARD"]["rate_pct"] = new_rate
        changes.append(f"International Card rate: {old_rate}% → {new_rate}%")
    
    # Wallet/BNPL rate change
    wallet_match = re.search(r'wallet.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if not wallet_match:
        wallet_match = re.search(r'bnpl.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if wallet_match:
        new_rate = float(wallet_match.group(1))
        old_rate = amended["rules"]["payment_methods"]["WALLET"].get("rate_pct", 2.1)
        amended["rules"]["payment_methods"]["WALLET"]["rate_pct"] = new_rate
        changes.append(f"Wallet/BNPL rate: {old_rate}% → {new_rate}%")
    
    # GST rate change
    gst_match = re.search(r'gst.*?(\d+(?:\.\d+)?)\s*%', prompt_lower)
    if gst_match:
        new_rate = float(gst_match.group(1))
        old_rate = amended["rules"]["statutory_tax"].get("gst_rate_pct", 18.0)
        amended["rules"]["statutory_tax"]["gst_rate_pct"] = new_rate
        changes.append(f"GST rate: {old_rate}% → {new_rate}%")
    
    # General "waive all" or "emergency relief"
    if "emergency" in prompt_lower or "waive all" in prompt_lower or "relief" in prompt_lower:
        if amended["rules"]["refund_policy"].get("standard_fee", 5.0) != 0.0:
            amended["rules"]["refund_policy"]["standard_fee"] = 0.0
            amended["rules"]["refund_policy"]["waived_fee"] = 0.0
            changes.append("Refund/late fees waived (emergency relief)")
        if amended["rules"]["instant_settlement"].get("rate_pct", 0.15) != 0.0:
            amended["rules"]["instant_settlement"]["rate_pct"] = 0.0
            changes.append("Instant settlement surcharges waived (emergency relief)")
    
    if not changes:
        changes.append("No recognized policy directive in prompt")
    
    return amended, changes

# -------------------------------------------------------------
# Standalone HTTP Server Fallback (Zero Dependencies Required)
# -------------------------------------------------------------
from http.server import HTTPServer, BaseHTTPRequestHandler
import mimetypes

class ReconcileHTTPHandler(BaseHTTPRequestHandler):
    def _send_response_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath: str, content_type: Optional[str] = None, download_name: Optional[str] = None):
        if not os.path.exists(filepath):
            self.send_error(404, f"File not found: {filepath}")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        if content_type:
            self.send_header("Content-Type", content_type)
        else:
            mime, _ = mimetypes.guess_type(filepath)
            self.send_header("Content-Type", mime or "application/octet-stream")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            index_path = str(STATIC_DIR / "index.html")
            self._send_file(index_path, "text/html; charset=utf-8")
            return

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            fpath = str(STATIC_DIR / rel)
            self._send_file(fpath)
            return

        if path == "/api/reconciliation":
            data = run_reconciliation(SETTLEMENT_PATH, batch_id="DEFAULT_RECON")
            self._send_response_json(data)
            return

        if path == "/api/sample-pdfs":
            self._send_response_json({"samples": SAMPLE_PDF_CATALOG})
            return

        if path.startswith("/api/download-statement/"):
            sample_id = path.split("/")[-1]
            found = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
            if found and os.path.exists(found["statement_file"]):
                self._send_file(found["statement_file"], "text/csv", f"account_statement_sample_{sample_id}.csv")
            elif found and os.path.exists(found["sample_statement_path"]):
                self._send_file(found["sample_statement_path"], "text/csv", f"account_statement_sample_{sample_id}.csv")
            else:
                self.send_error(404, f"Statement for sample {sample_id} not found")
            return

        if path == "/api/contract":
            with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
                contract_raw = f.read()
            _, rules_json = get_engine_and_rules()
            self._send_response_json({"contract_raw": contract_raw, "rules_json": rules_json})
            return

        if path == "/api/dispute-draft":
            draft_files = glob.glob("reports/dispute_draft_*.md")
            if draft_files:
                draft_files.sort(key=os.path.getmtime, reverse=True)
                with open(draft_files[0], "r", encoding="utf-8") as f:
                    self._send_response_json({"file": draft_files[0], "content": f.read()})
                return
            engine, rules_data = get_engine_and_rules()
            classifier = TransactionClassifier(engine)
            records = load_settlement_csv(SETTLEMENT_PATH)
            classified = classifier.classify_all(records)
            content = generate_dispute_draft(classified, rules_data, batch_id="LATEST")
            self._send_response_json({"file": "reports/dispute_draft_LATEST.md", "content": content})
            return

        if path == "/api/export-audit":
            audit_file = "reports/audit_trail.csv"
            if not os.path.exists(audit_file):
                run_reconciliation(SETTLEMENT_PATH)
            self._send_file(audit_file, "text/csv", "razorpay_fee_leakage_audit.csv")
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        if path == "/api/load-sample":
            try:
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                sample_id = str(payload.get("sample_id", "1"))
                sample = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
                if not sample:
                    self._send_response_json({"error": f"Sample {sample_id} not found"}, 404)
                    return

                # Load rules
                rules_data = None
                if os.path.exists(sample["rules_file"]):
                    with open(sample["rules_file"], "r", encoding="utf-8") as f:
                        rules_data = json.load(f)
                else:
                    rules_data = extract_rules_from_pdf_text("", sample["filename"])

                # Run reconciliation against statement
                recon = run_reconciliation(sample["statement_file"], rules_override=rules_data, batch_id=f"SAMPLE_{sample_id}")
                recon["sample_info"] = sample
                self._send_response_json(recon)
            except Exception as e:
                self._send_response_json({"error": str(e)}, 400)
            return

        if path == "/api/apply-nlp-policy":
            try:
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                prompt = str(payload.get("prompt", "")).strip()
                sample_id = str(payload.get("sample_id", "1"))
                
                if not prompt:
                    self._send_response_json({"error": "Prompt cannot be empty"}, 400)
                    return
                
                sample = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
                if not sample:
                    self._send_response_json({"error": "Sample not found"}, 404)
                    return
                
                # Load current rules
                rules_data = None
                if os.path.exists(sample["rules_file"]):
                    with open(sample["rules_file"], "r", encoding="utf-8") as f:
                        rules_data = json.load(f)
                else:
                    _, rules_data = get_engine_and_rules()
                
                # Apply policy changes
                amended_rules, applied_changes = apply_policy_prompt(rules_data, prompt)
                
                # Run reconciliation with amended rules
                recon = run_reconciliation(sample["statement_file"], rules_override=amended_rules, batch_id=f"POLICY_{sample_id}")
                recon["sample_info"] = sample
                recon["policy_metadata"] = {
                    "original_prompt": prompt,
                    "applied_changes": applied_changes
                }
                
                self._send_response_json(recon)
            except Exception as e:
                self._send_response_json({"error": str(e)}, 400)
            return

        if path in ["/api/upload-settlement", "/api/process-pdf"]:
            try:
                # Handle multipart/form-data or raw bytes
                content_type = self.headers.get("Content-Type", "")
                filename = "uploaded_file.dat"
                file_content = body_bytes

                if "multipart/form-data" in content_type:
                    boundary = content_type.split("boundary=")[-1].strip().encode("utf-8")
                    parts = body_bytes.split(b"--" + boundary)
                    for part in parts:
                        if b'filename="' in part:
                            header_part, body_part = part.split(b"\r\n\r\n", 1)
                            headers_str = header_part.decode("utf-8", errors="ignore")
                            m = re.search(r'filename="([^"]+)"', headers_str)
                            if m:
                                filename = m.group(1)
                            file_content = body_part.rstrip(b"\r\n--").rstrip(b"\r\n")
                            break

                temp_dir = "reports"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"temp_{filename}")
                with open(temp_path, "wb") as f:
                    f.write(file_content)

                # Process PDF or CSV
                if filename.lower().endswith(".pdf"):
                    pdf_text = extract_text_from_pdf(temp_path)
                    doc_type = detect_pdf_document_type(pdf_text, filename)

                    if doc_type == "contract":
                        rules_extracted = extract_rules_from_pdf_text(pdf_text, filename)
                        recon = run_reconciliation(SETTLEMENT_PATH, rules_override=rules_extracted, batch_id=f"PDF_CONTRACT_{filename}")
                        recon["doc_type"] = "contract"
                        recon["extracted_text_preview"] = pdf_text[:1500]
                        recon["filename"] = filename
                        self._send_response_json(recon)
                    else:
                        records = parse_statement_from_pdf_text(pdf_text, filename)
                        if not records:
                            # Use default loader fallback
                            records = load_settlement_csv(temp_path)
                        recon = run_reconciliation(records, batch_id=f"PDF_STATEMENT_{filename}")
                        recon["doc_type"] = "statement"
                        recon["extracted_text_preview"] = pdf_text[:1500]
                        recon["filename"] = filename
                        self._send_response_json(recon)
                else:
                    # CSV processing
                    recon = run_reconciliation(temp_path, batch_id=f"UPLOAD_{filename}")
                    recon["filename"] = filename
                    recon["doc_type"] = "statement"
                    self._send_response_json(recon)
            except Exception as e:
                self._send_response_json({"error": str(e)}, 400)
            return

        self.send_error(404, "Endpoint not found")

def start_server(port: int = 8000):
    # Try running FastAPI if installed, else fallback to HTTPServer
    try:
        import fastapi
        import uvicorn
        from fastapi import FastAPI, UploadFile, File, HTTPException
        from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles

        app = FastAPI(title="Razorpay Fee Leakage Detector")
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", response_class=HTMLResponse)
        def index():
            with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
                return f.read()

        @app.get("/api/reconciliation")
        def get_reconciliation():
            return run_reconciliation(SETTLEMENT_PATH)

        @app.get("/api/sample-pdfs")
        def get_samples():
            return {"samples": SAMPLE_PDF_CATALOG}

        @app.get("/api/download-statement/{sample_id}")
        def download_statement(sample_id: str):
            found = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
            if found and os.path.exists(found["statement_file"]):
                return FileResponse(found["statement_file"], media_type="text/csv", filename=f"account_statement_sample_{sample_id}.csv")
            raise HTTPException(status_code=404, detail="Statement not found")

        @app.post("/api/load-sample")
        def load_sample(payload: Dict[str, Any]):
            sample_id = str(payload.get("sample_id", "1"))
            sample = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
            if not sample:
                raise HTTPException(status_code=404, detail="Sample not found")
            rules_data = None
            if os.path.exists(sample["rules_file"]):
                with open(sample["rules_file"], "r", encoding="utf-8") as f:
                    rules_data = json.load(f)
            recon = run_reconciliation(sample["statement_file"], rules_override=rules_data, batch_id=f"SAMPLE_{sample_id}")
            recon["sample_info"] = sample
            return recon

        @app.post("/api/upload-settlement")
        async def upload_settlement(file: UploadFile = File(...)):
            contents = await file.read()
            temp_path = f"reports/temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(contents)
            return run_reconciliation(temp_path, batch_id=f"UPLOAD_{file.filename}")

        @app.post("/api/process-pdf")
        async def process_pdf_api(file: UploadFile = File(...)):
            contents = await file.read()
            temp_path = f"reports/temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(contents)
            pdf_text = extract_text_from_pdf(temp_path)
            doc_type = detect_pdf_document_type(pdf_text, file.filename)
            if doc_type == "contract":
                rules_extracted = extract_rules_from_pdf_text(pdf_text, file.filename)
                recon = run_reconciliation(SETTLEMENT_PATH, rules_override=rules_extracted, batch_id=f"PDF_CONTRACT_{file.filename}")
                recon["doc_type"] = "contract"
                recon["extracted_text_preview"] = pdf_text[:1500]
                recon["filename"] = file.filename
                return recon
            else:
                records = parse_statement_from_pdf_text(pdf_text, file.filename) or load_settlement_csv(temp_path)
                recon = run_reconciliation(records, batch_id=f"PDF_STATEMENT_{file.filename}")
                recon["doc_type"] = "statement"
                recon["extracted_text_preview"] = pdf_text[:1500]
                recon["filename"] = file.filename
                return recon

        @app.get("/api/contract")
        def get_contract_data():
            with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
                contract_raw = f.read()
            _, rules_json = get_engine_and_rules()
            return {"contract_raw": contract_raw, "rules_json": rules_json}

        @app.get("/api/dispute-draft")
        def get_dispute():
            draft_files = glob.glob("reports/dispute_draft_*.md")
            if draft_files:
                draft_files.sort(key=os.path.getmtime, reverse=True)
                with open(draft_files[0], "r", encoding="utf-8") as f:
                    return {"file": draft_files[0], "content": f.read()}
            return {"file": "reports/dispute_draft_LATEST.md", "content": ""}

        @app.get("/api/export-audit")
        def export_audit():
            return FileResponse("reports/audit_trail.csv", media_type="text/csv", filename="razorpay_fee_leakage_audit.csv")

        @app.post("/api/apply-nlp-policy")
        async def apply_nlp_policy(payload: Dict[str, Any]):
            prompt = str(payload.get("prompt", "")).strip()
            sample_id = str(payload.get("sample_id", "1"))
            
            if not prompt:
                raise HTTPException(status_code=400, detail="Prompt cannot be empty")

            sample = next((s for s in SAMPLE_PDF_CATALOG if s["id"] == sample_id or s["filename"] == sample_id), None)
            if not sample:
                raise HTTPException(status_code=404, detail="Sample not found")

            # Load current rules
            rules_data = None
            if os.path.exists(sample["rules_file"]):
                with open(sample["rules_file"], "r", encoding="utf-8") as f:
                    rules_data = json.load(f)
            else:
                engine, rules_data = get_engine_and_rules()

            # Parse natural language prompt and apply policy changes
            amended_rules, applied_changes = apply_policy_prompt(rules_data, prompt)

            # Run reconciliation with amended rules
            recon = run_reconciliation(sample["statement_file"], rules_override=amended_rules, batch_id=f"POLICY_{sample_id}")
            recon["sample_info"] = sample
            
            # Add policy metadata
            recon["policy_metadata"] = {
                "original_prompt": prompt,
                "applied_changes": applied_changes
            }
            
            return recon

        print(f"Starting FastAPI web server at http://localhost:{port} ...")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"Notice: FastAPI not active ({e}), running high-performance built-in HTTP server.")
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(("0.0.0.0", port), ReconcileHTTPHandler)
        print(f"Razorpay Fee Leakage Detector running at http://localhost:{port} ...")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()

if __name__ == "__main__":
    start_server(8000)
