from typing import Any, Dict, List, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from rag import driver as driver_module

VALID_PROPERTIES = {
    "Paper": ["title", "date", "citationCount", "abstract", "hasURL", "hasArXivId"],
    "Author": ["name", "hIndex"],
    "Category": ["name"],
    "Method": ["name", "description", "numberPapers", "introducedYear", "codeSnippet", "source"],
    "Task": ["name", "description"],
}


class FuzzySearchInput(BaseModel):
    """Input schema for fuzzy searching nodes in the knowledge graph."""
    node_type: Literal["Paper", "Author", "Category", "Method", "Task"] = Field(
        description="The type of node to search for"
    )
    search_query: str = Field(
        description=(
            "Search query string. Uses Neo4j full-text search with relevance scoring. "
            "Supports boolean operators (AND, OR, NOT) and wildcards (*). "
            "Searches across all indexed text fields for the node type. "
            "Examples: 'transformer attention', 'hinton', 'image classification', 'BERT*'"
        )
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of results to return (ordered by relevance)"
    )
    return_properties: List[str] = Field(
        description=(
            "Specific properties to return. Choose based on the node type."
            "Paper: title, date, citationCount, abstract, hasURL, hasArXivId | "
            "Author: name, hIndex | "
            "Category: name | "
            "Method: name, description, numberPapers, introducedYear, codeSnippet, source |"
            "Task: name, description."
        ),
        examples=[
            ["name", "description"],
            ["title", "abstract"],
            ["title", "date"],
            ["name", "numberPapers"]
        ]
    )

    @field_validator("return_properties")
    @classmethod
    def validate_properties(cls, v, info):
        if v is None:
            return v
        
        node_type = info.data.get("node_type")
        if node_type:
            valid_props = VALID_PROPERTIES.get(node_type, [])
            invalid = [p for p in v if p not in valid_props]
            if invalid:
                raise ValueError(
                    f"Invalid properties for {node_type}: {invalid}. "
                    f"Valid options: {valid_props}"
                )
        return v


@tool(args_schema=FuzzySearchInput)
def search_nodes(
    node_type: str,
    search_query: str,
    limit: int,
    return_properties: List[str]
) -> List[Dict[str, Any]]:
    """
    Search for nodes in the knowledge graph using full-text search with relevance
    scoring.

    This tool uses Neo4j full-text indices to find relevant nodes and returns them
    ordered by relevance score (highest first). Use this when you need to find nodes
    but don't know their exact identifiers.

    Search capabilities:
    - Case-insensitive matching across all indexed fields
    - Boolean operators: "transformer AND attention", "BERT OR GPT"
    - Wildcards: "transform*" matches transformer, transformers, etc.
    - Phrase matching: '"attention mechanism"' (with quotes in the query)
    - Relevance-ranked results

    The tool returns exact property values (e.g., exact paper titles with proper
    capitalization) AND the nodeId (unique identifier) that can be used with other
    graph traversal tools.

    Returns:
        List of matching nodes with their properties, nodeId, and relevance scores.
        Empty list if no matches found or if an error occurs.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _search_nodes_tx,
                node_type,
                search_query,
                limit,
                return_properties,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to search nodes"}]


def _search_nodes_tx(
    tx,
    node_type: str,
    search_query: str,
    limit: int,
    return_properties: List[str],
):
    """Transaction function to execute full-text search query."""
    index_map = {
        "Paper": "paper_title_search",
        "Author": "author_search",
        "Category": "category_search",
        "Method": "method_search",
        "Task": "task_search",
    }

    index_name = index_map.get(node_type)
    if not index_name:
        raise ValueError(f"No index found for node type: {node_type}")

    params = {
        "index_name": index_name,
        "search_query": search_query,
        "limit": limit
    }

    return_items = (
        ["node.nodeId AS nodeId"]
        + [f"node.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items) + ", score"

    query = f"""
    CALL db.index.fulltext.queryNodes($index_name, $search_query)
    YIELD node, score
    RETURN {return_clause}
    ORDER BY score DESC
    LIMIT $limit
    """

    result = tx.run(query, **params)

    records = []
    for record in result:
        node_data = {"nodeId": record["nodeId"]}
        node_data.update({prop: record[prop] for prop in return_properties})
        node_data["node_type"] = node_type
        node_data["relevance_score"] = record["score"]
        records.append(node_data)

    return records
