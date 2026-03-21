"""Customer Success & Churn Prevention vertical pack."""
from __future__ import annotations
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack


class CustomerSuccessPack(VerticalPack):
    id = "customer_success"
    name = "Customer Success & Churn Prevention"
    description = (
        "Health score signals, churn risk detection, expansion opportunity identification, "
        "QBR analysis, and CSM action planning from customer calls."
    )
    industries = ["SaaS", "Enterprise Software", "Financial Services",
                  "Healthcare SaaS", "EdTech", "HR Tech"]
    summary_type = "cs_qbr"

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="cs-pack-v1",
            name=self.name,
            description=self.description,
            vertical="customer_success",
            fields=[
                FieldDefinition("topic", FieldType.CATEGORY,
                                "Primary CS topic",
                                options=["product_usage", "support_issue", "renewal",
                                         "expansion", "adoption", "roi",
                                         "executive_alignment", "general"]),
                FieldDefinition("health_signal", FieldType.CATEGORY,
                                "Account health indicator from this segment",
                                options=["green", "yellow", "red"]),
                FieldDefinition("churn_risk", FieldType.CATEGORY,
                                "Churn risk level",
                                options=["low", "medium", "high", "churned"]),
                FieldDefinition("churn_risk_score", FieldType.NUMBER,
                                "Numeric churn risk 0.0–1.0"),
                FieldDefinition("churn_indicators", FieldType.LIST_STRING,
                                "Specific churn risk signals expressed"),
                FieldDefinition("expansion_signals", FieldType.LIST_STRING,
                                "Signals of growth or expansion opportunity",
                                required=False),
                FieldDefinition("objections", FieldType.LIST_STRING,
                                "Customer concerns or complaints raised"),
                FieldDefinition("decision_signals", FieldType.LIST_STRING,
                                "Positive engagement or commitment signals",
                                required=False),
                FieldDefinition("exec_sponsor_present", FieldType.BOOLEAN,
                                "Is an executive sponsor engaged in the call?",
                                required=False),
                FieldDefinition("product_usage_sentiment", FieldType.CATEGORY,
                                "How the customer describes product usage",
                                options=["heavy", "moderate", "light", "not_using"],
                                required=False),
                FieldDefinition("support_pain_points", FieldType.LIST_STRING,
                                "Specific product or support issues raised",
                                required=False),
                FieldDefinition("renewal_outlook", FieldType.CATEGORY,
                                "Renewal likelihood based on this call",
                                options=["likely", "uncertain", "at_risk", "churning"],
                                required=False),
                FieldDefinition("csm_action_items", FieldType.LIST_STRING,
                                "Specific actions the CSM should take after this call"),
            ],
        )
