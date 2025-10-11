from typing import Literal, Optional, List, Dict, Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module


class FuzzySearchInput(BaseModel):
    """Input schema for fuzzy searching nodes in the knowledge graph."""
    node_type: Literal["Paper", "Author", "Model", "Dataset", "Task", "Method"] = Field(
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
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return (ordered by relevance)"
    )
    return_properties: Optional[List[str]] = Field(
        description=(
            "Specific properties to return. Choose based on the node type."
            "Paper: title, date, abstract, hasUrl, hasArXivId | "
            "Author: name | "
            "Model: name, numberPapers | "
            "Dataset: name, description, numberPapers |"
            "Method: name, description, numberPapers, introducedYear, codeSnippet, source |"
            "Task: name."
        ),
        examples=[
            ["name", "description"],
            ["title", "abstract"],
            ["title", "date"],
            ["name", "numberPapers"]
        ]
    )


@tool(args_schema=FuzzySearchInput)
def search_nodes(
    node_type: str,
    search_query: str,
    limit: int = 10,
    return_properties: Optional[List[str]] = None
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
    capitalization) that can be used with other tools.

    Returns:
        List of matching nodes with their properties and relevance scores.
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
    return_properties: Optional[List[str]],
):
    """Transaction function to execute full-text search query."""
    index_map = {
        "Paper": "paper_search",
        "Author": "author_search",
        "Model": "model_search",
        "Dataset": "dataset_search",
        "Task": "task_search",
        "Method": "method_search",
    }

    index_name = index_map.get(node_type)
    if not index_name:
        raise ValueError(f"No index found for node type: {node_type}")

    default_properties = {
        "Paper": ["title", "date", "abstract", "hasArXivId", "hasUrl"],
        "Author": ["name"],
        "Model": ["name", "numberPapers", "introducedYear"],
        "Dataset": ["title", "description"],
        "Task": ["name", "description"],
        "Method": ["name", "description", "fullname", "numberPapers"],
    }
    props_to_return = return_properties or default_properties.get(node_type, ["name"])

    params = {
        "index_name": index_name,
        "search_query": search_query,
        "limit": limit
    }

    return_items = [f"node.{prop} AS {prop}" for prop in props_to_return]
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
        node_data = {prop: record[prop] for prop in props_to_return}
        node_data["node_type"] = node_type
        node_data["relevance_score"] = record["score"]
        records.append(node_data)

    return records
