from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module
from rag.tools.shared_models import PaperQueryParams

AUTHOR_NODE_ID = Field(
    description=(
        "Unique node identifier (nodeId) for the author, as returned by search_nodes. "
        "This is the stable URI identifier for the author node."
    )
)


class AuthorPapersInput(PaperQueryParams):
    """Input schema for finding papers by an author."""
    author_node_id: str = AUTHOR_NODE_ID


@tool(args_schema=AuthorPapersInput)
def author_papers(
    author_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all papers authored by a specific author.

    Traversal pattern: Author <- HAS_AUTHOR <- Paper

    Use this when you need to:
    - Find all publications by an author
    - Explore an author's research output
    - Get papers as input for further traversals (e.g., to find citations)

    Returns:
        List of papers with nodeId, requested properties, ordered by date or citation count.
        Empty list if author not found or has no papers.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _author_papers_tx,
                author_node_id,
                limit,
                return_properties,
                order_by,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve author papers"}]


def _author_papers_tx(
    tx,
    author_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "author_node_id": author_node_id,
        "limit": limit,
    }

    return_items = (
        ["paper.nodeId AS nodeId"]
        + [f"paper.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    where_conditions = ["author.nodeId = $author_node_id"]
    if date_from:
        where_conditions.append("paper.date >= $date_from")
        params["date_from"] = date_from
    if date_to:
        where_conditions.append("paper.date <= $date_to")
        params["date_to"] = date_to
    
    where_clause = "WHERE " + " AND ".join(where_conditions)

    if order_by == "date_desc":
        order_clause = "paper.date DESC"
    elif order_by == "date_asc":
        order_clause = "paper.date ASC"
    else:
        order_clause = "paper.citationCount DESC"

    query = f"""
    MATCH (author:Author)<-[:HAS_AUTHOR]-(paper:Paper)
    {where_clause}
    RETURN {return_clause}
    ORDER BY {order_clause}
    LIMIT $limit
    """

    result = tx.run(query, **params)

    records = []
    for record in result:
        paper_data = {"nodeId": record["nodeId"]}
        paper_data.update({prop: record[prop] for prop in return_properties})
        records.append(paper_data)

    return records


class AuthorCoauthorsInput(BaseModel):
    """Input schema for finding an author's collaborators."""
    author_node_id: str = AUTHOR_NODE_ID
    limit: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of coauthors to return"
    )
    min_collaborations: Optional[int] = Field(
        default=1,
        ge=1,
        description="Minimum number of co-authored papers required"
    )


@tool(args_schema=AuthorCoauthorsInput)
def author_coauthors(
    author_node_id: str,
    limit: int,
    min_collaborations: Optional[int] = 1
) -> List[Dict[str, Any]]:
    """
    Find an author's collaborators (coauthors).

    Traversal pattern: Author <- HAS_AUTHOR <- Paper -> HAS_AUTHOR -> Author
    (excluding the starting author)

    Returns coauthors with collaboration statistics:
    - nodeId: Unique identifier for the coauthor
    - name: Coauthor's name
    - collaboration_count: Number of papers co-authored together
    - first_collaboration: Date of earliest collaboration
    - last_collaboration: Date of most recent collaboration

    Use this when you need to:
    - Map an author's collaboration network
    - Find frequent collaborators
    - Understand research partnerships

    Returns:
        List of coauthors ordered by collaboration frequency (most frequent first).
        Empty list if author not found or has no collaborators.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _author_coauthors_tx,
                author_node_id,
                limit,
                min_collaborations
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve coauthors"}]


def _author_coauthors_tx(
    tx,
    author_node_id: str,
    limit: int,
    min_collaborations: int
):
    """Transaction function for finding coauthors."""
    query = """
    MATCH (author:Author {nodeId: $author_node_id})<-[:HAS_AUTHOR]-(paper:Paper)-[:HAS_AUTHOR]->(coauthor:Author)
    WHERE author <> coauthor
    WITH
        coauthor, 
        COUNT(paper) AS collaboration_count,
        MIN(paper.date) AS first_collaboration,
        MAX(paper.date) AS last_collaboration
    WHERE collaboration_count >= $min_collaborations
    RETURN
        coauthor.nodeId AS nodeId,
        coauthor.name AS name,
        coauthor.hIndex AS hIndex,
        collaboration_count,
        first_collaboration,
        last_collaboration
    ORDER BY collaboration_count DESC, last_collaboration DESC
    LIMIT $limit
    """

    result = tx.run(
        query,
        author_node_id=author_node_id,
        limit=limit,
        min_collaborations=min_collaborations
    )

    records = []
    for record in result:
        coauthor_data = {
            "nodeId": record["nodeId"],
            "name": record["name"],
            "hIndex": record["hIndex"],
            "collaboration_count": record["collaboration_count"],
            "first_collaboration": record["first_collaboration"],
            "last_collaboration": record["last_collaboration"]
        }
        records.append(coauthor_data)
    
    return records
