"""Tests for PDF extraction, classification, and statement ingestion."""

import os
import unittest
from src.pdf_processor import (
    extract_text_from_pdf,
    detect_pdf_document_type,
    extract_rules_from_pdf_text,
    parse_statement_from_pdf_text
)
from src.loader import load_settlement_csv
from src.engine import FeeCalculationEngine
from src.classifier import TransactionClassifier
from src.report import ReconciliationReporter

class TestPDFProcessing(unittest.TestCase):

    def test_sample_pdf_text_extraction(self):
        pdf_1 = "sample_pdf/1.pdf"
        self.assertTrue(os.path.exists(pdf_1), f"Sample PDF {pdf_1} not found")
        text_1 = extract_text_from_pdf(pdf_1)
        self.assertIn("Axos", text_1)
        self.assertIn("Fee Schedule", text_1)

        pdf_3 = "sample_pdf/3.pdf"
        self.assertTrue(os.path.exists(pdf_3), f"Sample PDF {pdf_3} not found")
        text_3 = extract_text_from_pdf(pdf_3)
        self.assertIn("Huntington", text_3)
        self.assertIn("Citibank", text_3)

        pdf_4 = "sample_pdf/4.pdf"
        self.assertTrue(os.path.exists(pdf_4), f"Sample PDF {pdf_4} not found")
        text_4 = extract_text_from_pdf(pdf_4)
        self.assertIn("eWRAP", text_4)

    def test_pdf_document_type_detection(self):
        contract_text = "Standard Fee Schedule and Merchant Pricing Annexure Agreement"
        statement_text = "Account Statement Settlement Report Date Txn ID Amount Fee Billed"
        self.assertEqual(detect_pdf_document_type(contract_text), "contract")
        self.assertEqual(detect_pdf_document_type(statement_text), "statement")

    def test_pdf_rule_extraction_sample_1(self):
        pdf_1 = "sample_pdf/1.pdf"
        text = extract_text_from_pdf(pdf_1)
        rules = extract_rules_from_pdf_text(text, "1.pdf")
        self.assertEqual(rules["contract_id"], "AXOS-FEE-2025")
        self.assertIn("payment_methods", rules["rules"])
        self.assertIn("DOMESTIC_CARD", rules["rules"]["payment_methods"])

    def test_pdf_rule_extraction_sample_3(self):
        pdf_3 = "sample_pdf/3.pdf"
        text = extract_text_from_pdf(pdf_3)
        rules = extract_rules_from_pdf_text(text, "3.pdf")
        self.assertEqual(rules["contract_id"], "HUNTINGTON-CITI-2012")
        self.assertIn("payment_methods", rules["rules"])

    def test_pdf_rule_extraction_sample_4(self):
        pdf_4 = "sample_pdf/4.pdf"
        text = extract_text_from_pdf(pdf_4)
        rules = extract_rules_from_pdf_text(text, "4.pdf")
        self.assertEqual(rules["contract_id"], "BTPANORAMA-EWRAP-2026")
        self.assertIn("payment_methods", rules["rules"])

    def test_generated_statements_reconciliation(self):
        # Test Sample 1 reconciliation
        rules_1 = extract_rules_from_pdf_text("", "1.pdf")
        stmt_1 = "data/statement_1_axos.csv"
        self.assertTrue(os.path.exists(stmt_1))
        records_1 = load_settlement_csv(stmt_1)
        self.assertGreater(len(records_1), 0)

        engine_1 = FeeCalculationEngine(rules_1)
        classifier_1 = TransactionClassifier(engine_1)
        classified_1 = classifier_1.classify_all(records_1)
        reporter_1 = ReconciliationReporter(classified_1)
        summary_1 = reporter_1.compute_summary()

        self.assertGreater(summary_1["total_records"], 0)
        self.assertGreater(summary_1["leak_count"], 0) # Seeded leaks should be detected
        self.assertGreater(summary_1["match_count"], 0) # Clean matches should match

if __name__ == "__main__":
    unittest.main()

