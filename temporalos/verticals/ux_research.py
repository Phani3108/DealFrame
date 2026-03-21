"""UX Research vertical pack."""
from __future__ import annotations
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack


class UXResearchPack(VerticalPack):
    id = "ux_research"
    name = "UX Research & User Interviews"
    description = (
        "Structured coding of user interviews and usability sessions — pain points, "
        "feature requests, confusion moments, delight signals, and task success."
    )
    industries = ["Product Management", "UX Design", "SaaS", "Consumer Apps",
                  "Healthcare UX", "Fintech", "EdTech"]
    summary_type = "ux_research"

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="ux-research-pack-v1",
            name=self.name,
            description=self.description,
            vertical="ux_research",
            fields=[
                FieldDefinition("segment_type", FieldType.CATEGORY,
                                "Type of observed moment",
                                options=["pain_point", "feature_request", "delight",
                                         "confusion", "task_attempt", "question",
                                         "comparison", "general"]),
                FieldDefinition("topic", FieldType.CATEGORY,
                                "Product area being discussed",
                                options=["onboarding", "core_workflow", "navigation",
                                         "search", "collaboration", "pricing",
                                         "integrations", "support", "general"]),
                FieldDefinition("pain_points", FieldType.LIST_STRING,
                                "User pain points expressed verbatim or paraphrased"),
                FieldDefinition("feature_requests", FieldType.LIST_STRING,
                                "Explicit or implicit feature requests"),
                FieldDefinition("confusion_signals", FieldType.LIST_STRING,
                                "Signs of confusion: hesitation, backtracking, questions",
                                required=False),
                FieldDefinition("delight_moments", FieldType.LIST_STRING,
                                "Positive reactions and moments of satisfaction",
                                required=False),
                FieldDefinition("task_success", FieldType.CATEGORY,
                                "Task completion outcome",
                                options=["success", "partial", "failure", "not_applicable"],
                                required=False),
                FieldDefinition("severity", FieldType.CATEGORY,
                                "Severity of the pain point (if any)",
                                options=["critical", "major", "minor", "none"],
                                required=False),
                FieldDefinition("sentiment", FieldType.CATEGORY,
                                "User emotional tone",
                                options=["positive", "neutral", "frustrated",
                                         "confused", "delighted"]),
                FieldDefinition("persona_signals", FieldType.LIST_STRING,
                                "Clues about user's role, experience level, or context",
                                required=False),
                FieldDefinition("verbatim_quote", FieldType.STRING,
                                "Most insightful direct quote from this segment",
                                required=False),
                FieldDefinition("competitive_mentions", FieldType.LIST_STRING,
                                "Competing tools or workflows mentioned", required=False),
            ],
        )
