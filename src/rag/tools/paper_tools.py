from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module


class PaperAuthorsInput(BaseModel):
    """Input schema for finding authors of a paper."""
    paper_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
            "This is the stable URI identifier for the paper node."
        )
    )
    return_properties: List[str] = Field(
        default=["name"],
        description=(
            "Properties to return for each author. Currently only 'name' is available."
        )
    )


@tool(args_schema=PaperAuthorsInput)
def paper_authors(
    paper_node_id: str,
    return_properties: List[str]
) -> List[Dict[str, Any]]:
    """
    Find all authors of a specific paper.

    Traversal pattern: Paper -> HAS_AUTHOR -> Author

    Use this when you need to:
    - Identify who wrote a paper
    - Find authors to explore their other work
    - Get authors as input for finding collaborators

    Returns:
        List of authors with nodeId and requested properties, in order of authorship.
        Empty list if paper not found or has no authors.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_authors_tx,
                paper_node_id,
                return_properties
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve paper authors"}]


def _paper_authors_tx(tx, paper_node_id: str, return_properties: List[str]):
    """Transaction function for paper_authors traversal."""
    return_items = (
        ["author.nodeId AS nodeId"]
        + [f"author.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    query = f"""
    MATCH (paper:Paper {{nodeId: $paper_node_id}})-[:HAS_AUTHOR]->(author:Author)
    RETURN {return_clause}
    """

    result = tx.run(query, paper_node_id=paper_node_id)

    records = []
    for record in result:
        author_data = {"nodeId": record["nodeId"]}
        author_data.update({prop: record[prop] for prop in return_properties})
        records.append(author_data)

    return records
