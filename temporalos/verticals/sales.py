"""Sales & Revenue Intelligence vertical pack."""
from __future__ import annotations
import uuid
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack


class SalesPack(VerticalPack):
    id = "sales"
    name = "Sales"
    description = (
        "Deep sales call analysis — objections, pricing signals, deal risk scoring, "
        "rep benchmarks, talk ratio, and next-step discovery."
    )
    industries = ["SaaS", "Enterprise Sales", "Insurance", "Real Estate Sales",
                  "Financial Services", "Recruiting"]
    summary_type = "deal_brief"

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="sales-pack-v1",
            name=self.name,
            description=self.description,
            vertical="sales",
            fields=[
                FieldDefinition("topic", FieldType.CATEGORY, "Primary topic of the segment",
                                options=["pricing", "competition", "features", "timeline",
                                         "security", "onboarding", "support", "general"]),
                FieldDefinition("sentiment", FieldType.CATEGORY, "Customer sentiment",
                                options=["positive", "neutral", "negative", "hesitant"]),
                FieldDefinition("risk", FieldType.CATEGORY, "Deal risk level",
                                options=["low", "medium", "high"]),
                FieldDefinition("risk_score", FieldType.NUMBER,
                                "Numeric risk 0.0–1.0"),
                FieldDefinition("objections", FieldType.LIST_STRING,
                                "Sales objections raised"),
                FieldDefinition("decision_signals", FieldType.LIST_STRING,
                                "Forward-motion buying signals"),
                FieldDefinition("pricing_mentions", FieldType.LIST_STRING,
                                "Specific prices, discounts, or budget figures mentioned",
                                required=False),
                FieldDefinition("competitor_mentions", FieldType.LIST_STRING,
                                "Competitors or alternatives named", required=False),
                FieldDefinition("champion_present", FieldType.BOOLEAN,
                                "Is an internal champion / decision-maker present?",
                                required=False),
                FieldDefinition("deal_stage", FieldType.CATEGORY,
                                "Inferred deal stage",
                                options=["discovery", "demo", "evaluation",
                                         "negotiation", "closed-won", "closed-lost"],
                                required=False),
                FieldDefinition("rep_talk_percentage", FieldType.NUMBER,
                                "Rep's share of speaking time (0–100)", required=False),
                FieldDefinition("urgency_level", FieldType.CATEGORY,
                                "Customer urgency signal",
                                options=["low", "medium", "high"], required=False),
            ],
        )
