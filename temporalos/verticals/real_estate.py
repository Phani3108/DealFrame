"""Real Estate client consultation vertical pack."""
from __future__ import annotations
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack


class RealEstatePack(VerticalPack):
    id = "real_estate"
    name = "Real Estate Client Consultations"
    description = (
        "Extract client priorities, budget signals, property objections, timeline urgency, "
        "and decision criteria from real estate consultations and walkthroughs."
    )
    industries = ["Residential Real Estate", "Commercial Real Estate",
                  "Property Management", "Mortgage Brokerage"]
    summary_type = "real_estate_consult"

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="real-estate-pack-v1",
            name=self.name,
            description=self.description,
            vertical="real_estate",
            fields=[
                FieldDefinition("topic", FieldType.CATEGORY,
                                "Primary consultation topic",
                                options=["property_features", "pricing_negotiation",
                                         "location", "timeline", "financing",
                                         "comparison", "objections", "general"]),
                FieldDefinition("client_priorities", FieldType.LIST_STRING,
                                "Property features or requirements the client emphasized"),
                FieldDefinition("budget_signals", FieldType.LIST_STRING,
                                "Budget range, financing concerns, or price sensitivity signals",
                                required=False),
                FieldDefinition("property_objections", FieldType.LIST_STRING,
                                "Specific property concerns or dislikes raised"),
                FieldDefinition("timeline_urgency", FieldType.CATEGORY,
                                "How urgently the client needs to move",
                                options=["immediately", "1_month", "3_months",
                                         "6_months", "flexible", "just_browsing"]),
                FieldDefinition("decision_criteria", FieldType.LIST_STRING,
                                "Must-have criteria the client stated",
                                required=False),
                FieldDefinition("sentiment", FieldType.CATEGORY,
                                "Overall client sentiment for this property/segment",
                                options=["very_positive", "positive", "neutral",
                                         "negative", "very_negative"]),
                FieldDefinition("comparison_properties", FieldType.LIST_STRING,
                                "Other properties mentioned for comparison",
                                required=False),
                FieldDefinition("financing_status", FieldType.CATEGORY,
                                "Client's financing situation",
                                options=["pre_approved", "in_progress", "cash_buyer",
                                         "needs_mortgage", "unknown"],
                                required=False),
                FieldDefinition("decision_signals", FieldType.LIST_STRING,
                                "Signs of interest or readiness to proceed",
                                required=False),
                FieldDefinition("risk_score", FieldType.NUMBER,
                                "Likelihood of losing this client (0.0–1.0)"),
                FieldDefinition("recommended_follow_up", FieldType.LIST_STRING,
                                "Specific follow-up actions for the agent"),
            ],
        )
