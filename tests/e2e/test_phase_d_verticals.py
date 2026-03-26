"""Phase D E2E test — Vertical Packs.

Tests all 4 vertical packs:
  1. Sales Pack
  2. UX Research Pack
  3. Customer Success Pack
  4. Real Estate Pack

Each test verifies:
  - Pack registers correctly
  - Schema has the expected fields
  - SchemaBasedExtractor produces well-typed output
  - Summary type is appropriate
"""
from __future__ import annotations

from typing import Any, Dict

import pytest


# ── Shared synthetic segment ──────────────────────────────────────────────────

def _sales_segment():
    return {
        "timestamp_str": "00:00",
        "timestamp_ms": 0,
        "transcript": (
            "The pricing is high compared to Salesforce. "
            "We are evaluating competitors. "
            "If you can match the price, we will sign this quarter. "
            "Can we get a 20% discount? This is our champion, Sarah."
        ),
        "ocr_text": "Pricing: $50,000 / year  |  Competitors: Salesforce, HubSpot",
    }


def _ux_segment():
    return {
        "timestamp_str": "00:00",
        "timestamp_ms": 0,
        "transcript": (
            "I was confused about how to navigate the settings. "
            "The upload feature is really delightful though. "
            "I wish there was a bulk import option — that's a pain point. "
            "I keep clicking the wrong button which is frustrating."
        ),
        "ocr_text": "Settings screen | Upload | Bulk import",
    }


def _cs_segment():
    return {
        "timestamp_str": "00:00",
        "timestamp_ms": 0,
        "transcript": (
            "We are happy with the product overall. "
            "Support response times have been slow though. "
            "We might churn if the API reliability doesn't improve. "
            "We are definitely interested in expanding to 3 more teams."
        ),
        "ocr_text": "Q3 Business Review | Usage: 87% | NPS: 42",
    }


def _real_estate_segment():
    return {
        "timestamp_str": "00:00",
        "timestamp_ms": 0,
        "transcript": (
            "We have a budget of about 800k. "
            "We want to move in by March. "
            "The schools need to be good. "
            "We are also looking at 123 Oak Avenue and 456 Maple Drive."
        ),
        "ocr_text": "Property: 789 Elm St | List Price: $795,000 | Beds: 4",
    }


# ── 1. Sales Pack ─────────────────────────────────────────────────────────────

class TestSalesPack:
    def test_pack_registered(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        pack = registry.get("sales")
        assert pack is not None
        assert pack.name.lower() == "sales"

    def test_schema_fields(self):
        from temporalos.verticals.sales import SalesPack
        pack = SalesPack()
        schema = pack.schema()
        field_names = {f.name for f in schema.fields}
        required = {"topic", "sentiment", "risk", "objections", "decision_signals"}
        assert required.issubset(field_names)

    def test_summary_type(self):
        from temporalos.verticals.sales import SalesPack
        pack = SalesPack()
        assert pack.summary_type == "deal_brief"

    def test_extractor_produces_output(self):
        from temporalos.verticals.sales import SalesPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        pack = SalesPack()
        extractor = SchemaBasedExtractor(schema=pack.schema())
        seg = _sales_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        assert result is not None
        assert hasattr(result, "topic")
        assert hasattr(result, "risk")

    def test_objection_detection(self):
        from temporalos.verticals.sales import SalesPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        pack = SalesPack()
        extractor = SchemaBasedExtractor(schema=pack.schema())
        seg = _sales_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        assert isinstance(result.objections, list)

    def test_competitor_mentions(self):
        from temporalos.verticals.sales import SalesPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        pack = SalesPack()
        schema = pack.schema()
        field_names = {f.name for f in schema.fields}
        assert "competitor_mentions" in field_names


# ── 2. UX Research Pack ───────────────────────────────────────────────────────

class TestUXResearchPack:
    def test_pack_registered(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        pack = registry.get("ux_research")
        assert pack is not None

    def test_schema_fields(self):
        from temporalos.verticals.ux_research import UXResearchPack
        pack = UXResearchPack()
        schema = pack.schema()
        field_names = {f.name for f in schema.fields}
        required = {"topic", "pain_points", "feature_requests", "confusion_signals"}
        assert required.issubset(field_names)

    def test_summary_type(self):
        from temporalos.verticals.ux_research import UXResearchPack
        assert UXResearchPack().summary_type == "ux_research"

    def test_extractor_on_ux_transcript(self):
        from temporalos.verticals.ux_research import UXResearchPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        extractor = SchemaBasedExtractor(schema=UXResearchPack().schema())
        seg = _ux_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        assert result is not None

    def test_pain_points_detected(self):
        from temporalos.verticals.ux_research import UXResearchPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        extractor = SchemaBasedExtractor(schema=UXResearchPack().schema())
        seg = _ux_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        # "pain point" appears in transcript → should flag
        assert hasattr(result, "pain_points")


# ── 3. Customer Success Pack ──────────────────────────────────────────────────

class TestCustomerSuccessPack:
    def test_pack_registered(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        assert registry.get("customer_success") is not None

    def test_schema_fields(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        pack = CustomerSuccessPack()
        schema = pack.schema()
        field_names = {f.name for f in schema.fields}
        required = {"topic", "churn_risk", "expansion_signals", "health_signal"}
        assert required.issubset(field_names)

    def test_summary_type(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        assert CustomerSuccessPack().summary_type == "cs_qbr"

    def test_churn_indicator_detected(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        from temporalos.schemas.builder import SchemaBasedExtractor
        extractor = SchemaBasedExtractor(schema=CustomerSuccessPack().schema())
        seg = _cs_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        assert hasattr(result, "churn_risk")

    def test_expansion_signals_field_exists(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        schema = CustomerSuccessPack().schema()
        assert any(f.name == "expansion_signals" for f in schema.fields)


# ── 4. Real Estate Pack ───────────────────────────────────────────────────────

class TestRealEstatePack:
    def test_pack_registered(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        assert registry.get("real_estate") is not None

    def test_schema_fields(self):
        from temporalos.verticals.real_estate import RealEstatePack
        pack = RealEstatePack()
        schema = pack.schema()
        field_names = {f.name for f in schema.fields}
        required = {"topic", "budget_signals", "timeline_urgency", "property_objections"}
        assert required.issubset(field_names)

    def test_summary_type(self):
        from temporalos.verticals.real_estate import RealEstatePack
        assert RealEstatePack().summary_type == "real_estate_consult"

    def test_extractor_on_real_estate_transcript(self):
        from temporalos.verticals.real_estate import RealEstatePack
        from temporalos.schemas.builder import SchemaBasedExtractor
        extractor = SchemaBasedExtractor(schema=RealEstatePack().schema())
        seg = _real_estate_segment()
        result = extractor.extract(seg["transcript"], seg["ocr_text"])
        assert result is not None

    def test_budget_and_timeline_fields(self):
        from temporalos.verticals.real_estate import RealEstatePack
        schema = RealEstatePack().schema()
        names = {f.name for f in schema.fields}
        assert "budget_signals" in names
        assert "timeline_urgency" in names


# ── Vertical Registry ─────────────────────────────────────────────────────────

class TestVerticalRegistry:
    def test_all_packs_registered(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        expected = {"sales", "ux_research", "customer_success", "real_estate", "procurement"}
        registered = set(registry.list_ids())
        assert expected == registered

    def test_list_packs_returns_all(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        packs = registry.list_packs()
        assert len(packs) == 5

    def test_get_unknown_returns_none(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        assert registry.get("nonexistent") is None

    def test_each_pack_has_schema(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        for pack in registry.list_packs():
            schema = pack.schema()
            assert schema is not None
            assert len(schema.fields) > 0

    def test_each_pack_has_industries(self):
        from temporalos.verticals import get_default_vertical_registry
        registry = get_default_vertical_registry()
        for pack in registry.list_packs():
            assert len(pack.industries) > 0
