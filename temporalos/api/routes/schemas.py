"""Custom Schema Builder API routes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...schemas.registry import FieldDefinition, FieldType, SchemaDefinition, get_schema_registry

router = APIRouter(prefix="/schemas", tags=["schemas"])


class FieldDefRequest(BaseModel):
    name: str
    type: str
    description: str = ""
    required: bool = False
    options: List[str] = []
    default: Optional[Any] = None


class SchemaCreateRequest(BaseModel):
    name: str
    vertical: str = ""
    fields: List[FieldDefRequest]


class SchemaUpdateRequest(BaseModel):
    name: Optional[str] = None
    vertical: Optional[str] = None
    fields: Optional[List[FieldDefRequest]] = None


@router.get("")
async def list_schemas() -> dict:
    registry = get_schema_registry()
    schemas = registry.list_schemas()
    return {"schemas": [s.to_dict() for s in schemas], "total": len(schemas)}


@router.post("")
async def create_schema(req: SchemaCreateRequest) -> dict:
    registry = get_schema_registry()

    fields: List[FieldDefinition] = []
    for f in req.fields:
        try:
            ftype = FieldType(f.type)
        except ValueError:
            valid = [t.value for t in FieldType]
            raise HTTPException(400, f"Invalid field type '{f.type}'. Valid: {valid}")
        fields.append(FieldDefinition(
            name=f.name,
            type=ftype,
            description=f.description,
            required=f.required,
            options=f.options,
            default=f.default,
        ))

    schema = SchemaDefinition(name=req.name, vertical=req.vertical, fields=fields)
    created = registry.create(schema)
    return {"schema": created.to_dict()}


@router.get("/{schema_id}")
async def get_schema(schema_id: str) -> dict:
    registry = get_schema_registry()
    schema = registry.get(schema_id)
    if not schema:
        raise HTTPException(404, f"Schema '{schema_id}' not found")
    return {"schema": schema.to_dict()}


@router.patch("/{schema_id}")
async def update_schema(schema_id: str, req: SchemaUpdateRequest) -> dict:
    registry = get_schema_registry()
    schema = registry.get(schema_id)
    if not schema:
        raise HTTPException(404, f"Schema '{schema_id}' not found")

    if req.name is not None:
        schema.name = req.name
    if req.vertical is not None:
        schema.vertical = req.vertical
    if req.fields is not None:
        fields: List[FieldDefinition] = []
        for f in req.fields:
            try:
                ftype = FieldType(f.type)
            except ValueError:
                raise HTTPException(400, f"Invalid field type '{f.type}'")
            fields.append(FieldDefinition(
                name=f.name, type=ftype, description=f.description,
                required=f.required, options=f.options, default=f.default,
            ))
        schema.fields = fields

    updated = registry.update(schema)
    return {"schema": updated.to_dict()}


@router.delete("/{schema_id}")
async def delete_schema(schema_id: str) -> dict:
    registry = get_schema_registry()
    ok = registry.delete(schema_id)
    if not ok:
        raise HTTPException(404, f"Schema '{schema_id}' not found")
    return {"deleted": True, "schema_id": schema_id}


@router.post("/{schema_id}/preview")
async def preview_schema_prompt(schema_id: str,
                                transcript: str = "",
                                ocr_text: str = "") -> dict:
    """Return the extraction prompt that would be sent to the LLM for this schema."""
    from ...schemas.builder import build_prompt_from_schema
    registry = get_schema_registry()
    schema = registry.get(schema_id)
    if not schema:
        raise HTTPException(404, f"Schema '{schema_id}' not found")
    prompt = build_prompt_from_schema(schema, transcript, ocr_text)
    return {"schema_id": schema_id, "prompt": prompt}
