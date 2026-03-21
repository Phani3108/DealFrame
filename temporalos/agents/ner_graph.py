"""NER-powered Knowledge Graph — LLM-based entity extraction.

Replaces keyword matching with LLM structured extraction for entities:
Person, Company, Product, Competitor, Price, Date, Feature.
Wraps existing KnowledgeGraph, adding LLM entity extraction + DB persistence.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .knowledge_graph import KGEdge, KGNode, KnowledgeGraph, get_knowledge_graph
from ..llm.router import get_llm

logger = logging.getLogger(__name__)

NER_SYSTEM = """\
You are an NER extraction system. Extract entities from the given text segment. \
Return a JSON array of objects: [{"entity": "name", "type": "person|company|product|competitor|price|date|feature|topic"}]. \
Extract ALL entities you can find. Be specific — "Salesforce" is a company, "$499/mo" is a price. \
Return only the JSON array, no other text.\
"""

NER_PROMPT = """\
Segment context:
Topic: {topic}
Transcript: {transcript}
Objections: {objections}
Decision signals: {signals}

Extract all entities from the above segment.\
"""


async def extract_entities_llm(segment: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Use LLM to extract named entities from a segment."""
    ext = segment.get("extraction", segment)
    prompt = NER_PROMPT.format(
        topic=ext.get("topic", "general"),
        transcript=segment.get("transcript", "")[:500],
        objections=", ".join(ext.get("objections", [])),
        signals=", ".join(ext.get("decision_signals", [])),
    )

    llm = get_llm()
    try:
        result = await llm.complete_json(
            prompt=prompt, system=NER_SYSTEM,
            temperature=0.0, max_tokens=512,
        )
        if isinstance(result, list):
            entities = result
        elif isinstance(result, dict) and "entities" in result:
            entities = result["entities"]
        else:
            entities = []

        return [
            (e.get("entity", "").strip()[:60], e.get("type", "entity").strip().lower())
            for e in entities
            if e.get("entity")
        ]
    except Exception as e:
        logger.warning("LLM NER failed: %s, falling back to keywords", e)
        return _fallback_ner(segment)


def _fallback_ner(segment: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Keyword-based fallback NER."""
    ext = segment.get("extraction", segment)
    entities: List[Tuple[str, str]] = []
    topic = ext.get("topic", "general")
    entities.append((topic, "topic"))
    for obj in ext.get("objections", [])[:3]:
        entities.append((obj.lower().strip()[:40], "objection"))
    for sig in ext.get("decision_signals", [])[:3]:
        entities.append((sig.lower().strip()[:40], "signal"))
    return entities


async def add_video_with_ner(
    kg: KnowledgeGraph,
    job_id: str,
    intel: Dict[str, Any],
) -> int:
    """Index a video into the KG using LLM-based NER."""
    segments = intel.get("segments", [])
    entity_count = 0

    for seg in segments:
        entities = await extract_entities_llm(seg)
        entity_nodes: List[str] = []

        for entity, etype in entities:
            nid = f"{etype}:{entity}"
            if nid not in kg._nodes:
                kg._nodes[nid] = KGNode(id=nid, entity_type=etype, label=entity)
            kg._nodes[nid].jobs.add(job_id)
            kg._nodes[nid].frequency += 1
            entity_nodes.append(nid)
            entity_count += 1

        # Co-occurrence edges
        for i, a in enumerate(entity_nodes):
            for b in entity_nodes[i + 1:]:
                if a == b:
                    continue
                edge_key = (min(a, b), max(a, b))
                if edge_key not in kg._edges:
                    kg._edges[edge_key] = KGEdge(source=edge_key[0], target=edge_key[1])
                else:
                    kg._edges[edge_key].weight += 1

    return entity_count


async def query_entity_llm(
    kg: KnowledgeGraph,
    question: str,
) -> Dict[str, Any]:
    """Answer a natural-language KG query using the graph + LLM."""
    graph_data = kg.query(question)
    if not graph_data.get("nodes"):
        return {
            "query": question,
            "answer": f"No entities found matching '{question}' in the knowledge graph.",
            "graph": graph_data,
        }

    # Build context from graph
    node_summaries = [
        f"- {n['label']} ({n['type']}, freq={n['frequency']}, jobs={len(n.get('jobs', []))})"
        for n in graph_data["nodes"][:15]
    ]
    edge_summaries = [
        f"- {e['source']} ↔ {e['target']} (weight={e['weight']})"
        for e in graph_data["edges"][:15]
    ]

    context = (
        f"Entities:\n" + "\n".join(node_summaries) +
        f"\n\nRelationships:\n" + "\n".join(edge_summaries)
    )

    llm = get_llm()
    try:
        resp = await llm.complete(
            prompt=f"Question: {question}\n\nKnowledge graph context:\n{context}\n\n"
                   "Answer the question based on the knowledge graph data.",
            system="You answer questions about entities and relationships found in video calls.",
            temperature=0.1, max_tokens=512,
        )
        answer = resp.text.strip()
    except Exception:
        answer = f"Found {len(graph_data['nodes'])} entities and {len(graph_data['edges'])} relationships."

    return {"query": question, "answer": answer, "graph": graph_data}
