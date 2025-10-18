from typing import Any, Dict, List

from langchain_core.tools import tool
from pydantic import BaseModel

from rag import driver as driver_module
from rag.tools import shared_models


class PaperAuthorsInput(BaseModel):
    """Input schema for finding authors of a paper."""
    paper_node_id: str = shared_models.PAPER_NODE_ID


@tool(args_schema=PaperAuthorsInput)
def paper_authors(paper_node_id: str) -> List[Dict[str, Any]]:
    """
    Find all authors of a specific paper.

    Traversal pattern: Paper -> HAS_AUTHOR -> Author

    Use this when you need to:
    - Identify who wrote a paper
    - Find authors to explore their other work
    - Get authors as input for finding collaborators

    Returns:
        List of authors with nodeId, name, and hIndex, in order of hIndex.
        Empty list if paper not found or has no authors.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_authors_tx,
                paper_node_id,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve paper authors"}]


def _paper_authors_tx(tx, paper_node_id: str):
    """Transaction function for paper_authors traversal."""
    query = """
    MATCH (paper:Paper {nodeId: $paper_node_id})-[:HAS_AUTHOR]->(author:Author)
    RETURN
        author.nodeId AS nodeId,
        author.name AS name,
        author.hIndex AS hIndex
    ORDER BY author.hIndex DESC
    """

    result = tx.run(query, paper_node_id=paper_node_id)

    records = []
    for record in result:
        author_data = {
            "nodeId": record["nodeId"],
            "name": record["name"],
            "hIndex": record["hIndex"]
        }
        records.append(author_data)

    return records
