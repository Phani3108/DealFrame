"""Base class for vertical packs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition


class VerticalPack(ABC):
    """A vertical pack bundles a schema, summary type preference, and metadata."""

    id: str = ""
    name: str = ""
    description: str = ""
    industries: List[str] = []
    summary_type: str = "meeting_notes"

    @abstractmethod
    def schema(self) -> SchemaDefinition:
        """Return the SchemaDefinition for this vertical."""
        ...

    def to_dict(self) -> dict:
        schema_dict = self.schema().to_dict()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "industries": self.industries,
            "summary_type": self.summary_type,
            "field_count": len(schema_dict["fields"]),
            "fields": schema_dict["fields"],
        }


class VerticalPackRegistry:
    def __init__(self) -> None:
        self._packs: Dict[str, VerticalPack] = {}

    def register(self, pack: VerticalPack) -> None:
        self._packs[pack.id] = pack

    def get(self, pack_id: str) -> Optional[VerticalPack]:
        return self._packs.get(pack_id)

    def list(self) -> List[VerticalPack]:
        return list(self._packs.values())

    def list_packs(self) -> List[VerticalPack]:
        return list(self._packs.values())

    def list_ids(self) -> List[str]:
        return list(self._packs.keys())


def get_vertical_registry() -> VerticalPackRegistry:
    from temporalos.verticals import get_default_vertical_registry
    return get_default_vertical_registry()
