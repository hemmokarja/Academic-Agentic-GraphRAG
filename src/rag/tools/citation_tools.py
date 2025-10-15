from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module


class PaperCitationsOutInput(BaseModel):
    """Input schema for finding papers that a given paper cites (references)."""
    paper_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
            "This is the stable URI identifier for the paper node."
        )
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of cited papers to return"
    )
    return_properties: List[str] = Field(
        default=["title", "date", "citationCount"],
        description=(
            "Properties to return for each cited paper. "
            "Available: title, date, citationCount, abstract, hasURL, hasArXivId"
        )
    )
    order_by: Optional[Literal["date", "citationCount"]] = Field(
        default="citationCount",
        description="Sort by date (newest first) or citation count (highest first)"
    )


@tool(args_schema=PaperCitationsOutInput)
def paper_citations_out(
    paper_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Find papers that are cited by (referenced in) a specific paper.

    Traversal pattern: Paper -> CITES -> Paper
    Direction: Outbound (this paper's references/bibliography)

    Use this when you need to:
    - Find what prior work influenced this paper
    - Explore the paper's theoretical foundations
    - Trace back the lineage of ideas

    Returns:
        List of cited papers with nodeId and requested properties.
        Empty list if paper not found or cites no papers.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_citations_out_tx,
                paper_node_id,
                limit,
                return_properties,
                order_by
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve citations"}]


def _paper_citations_out_tx(
    tx,
    paper_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str]
):
    """Transaction function for outbound citations."""
    return_items = (
        ["cited.nodeId AS nodeId"]
        + [f"cited.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    order_clause = (
        "cited.date DESC" if order_by == "date" else "cited.citationCount DESC"
    )

    query = f"""
    MATCH (paper:Paper {{nodeId: $paper_node_id}})-[:CITES]->(cited:Paper)
    RETURN {return_clause}
    ORDER BY {order_clause}
    LIMIT $limit
    """

    result = tx.run(query, paper_node_id=paper_node_id, limit=limit)

    records = []
    for record in result:
        paper_data = {"nodeId": record["nodeId"]}
        paper_data.update({prop: record[prop] for prop in return_properties})
        records.append(paper_data)

    return records


class PaperCitationsInInput(BaseModel):
    """Input schema for finding papers that cite a given paper."""
    paper_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
            "This is the stable URI identifier for the paper node."
        )
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of citing papers to return"
    )
    return_properties: List[str] = Field(
        default=["title", "date", "citationCount"],
        description=(
            "Properties to return for each citing paper. "
            "Available: title, date, citationCount, abstract, hasURL, hasArXivId"
        )
    )
    order_by: Optional[Literal["date", "citationCount"]] = Field(
        default="date",
        description="Sort by date (newest first) or citation count (highest first)"
    )


@tool(args_schema=PaperCitationsInInput)
def paper_citations_in(
    paper_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Find papers that cite a specific paper.

    Traversal pattern: Paper <- CITES <- Paper
    Direction: Inbound (papers that reference this paper)

    Use this when you need to:
    - Find what later work built upon this paper
    - Measure impact and influence
    - Discover related or derivative research

    Returns:
        List of citing papers with nodeId and requested properties.
        Empty list if paper not found or has no citations.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_citations_in_tx,
                paper_node_id,
                limit,
                return_properties,
                order_by
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve citing papers"}]


def _paper_citations_in_tx(
    tx,
    paper_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str]
):
    """Transaction function for inbound citations."""
    return_items = (
        ["citing.nodeId AS nodeId"]
        + [f"citing.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    order_clause = (
        "citing.date DESC" if order_by == "date" else "citing.citationCount DESC"
    )

    query = f"""
    MATCH (paper:Paper {{nodeId: $paper_node_id}})<-[:CITES]-(citing:Paper)
    RETURN {return_clause}
    ORDER BY {order_clause}
    LIMIT $limit
    """

    result = tx.run(query, paper_node_id=paper_node_id, limit=limit)

    records = []
    for record in result:
        paper_data = {"nodeId": record["nodeId"]}
        paper_data.update({prop: record[prop] for prop in return_properties})
        records.append(paper_data)

    return records


class PaperCitationChainInput(BaseModel):
    """Input schema for multi-hop citation traversal."""
    paper_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
            "This is the stable URI identifier for the paper node."
        )
    )
    direction: Literal["forward", "backward", "both"] = Field(
        description=(
            "Citation chain direction:\n"
            "- 'forward': Papers that cite this paper (influence/impact)\n"
            "- 'backward': Papers this paper cites (foundations/lineage)\n"
            "- 'both': All connected papers in citation network"
        )
    )
    max_depth: int = Field(
        default=2,
        ge=1,
        le=4,
        description=(
            "Maximum traversal depth (number of citation hops). "
            "Warning: depth > 3 can be extremely slow!"
        )
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum total papers to return across all depths"
    )
    return_properties: List[str] = Field(
        default=["title", "date", "citationCount"],
        description=(
            "Properties to return for each paper. "
            "Available: title, date, citationCount, abstract, hasURL, hasArXivId"
        )
    )


@tool(args_schema=PaperCitationChainInput)
def paper_citation_chain(
    paper_node_id: str,
    direction: str,
    max_depth: int,
    limit: int,
    return_properties: List[str]
) -> List[Dict[str, Any]]:
    """
    Traverse citation chains to explore research lineage or impact.

    Multi-hop traversal patterns:
    - Forward: Paper <- CITES <- Paper ← CITES <- ... (impact propagation)
    - Backward: Paper -> CITES -> Paper -> CITES -> ... (foundation tracing)
    - Both: Bidirectional citation network exploration

    Returns papers with:
    - nodeId: Unique identifier for each paper
    - All requested properties
    - depth: How many hops from the starting paper (1, 2, 3, ...)
    - path_length: Same as depth (for clarity)

    Use this when you need to:
    - Trace intellectual lineage backward through references
    - Follow impact forward through citing papers
    - Explore citation neighborhoods
    - Find papers N-degrees away in the citation network

    Returns:
        List of papers in the citation chain, ordered by depth then citation count.
        Empty list if paper not found or has no citations in the specified direction.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_citation_chain_tx,
                paper_node_id,
                direction,
                max_depth,
                limit,
                return_properties
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to traverse citation chain"}]


def _paper_citation_chain_tx(
    tx,
    paper_node_id: str,
    direction: str,
    max_depth: int,
    limit: int,
    return_properties: List[str]
):
    """Transaction function for citation chain traversal."""
    # Build the relationship pattern based on direction
    if direction == "forward":
        rel_pattern = "<-[:CITES*1..{}]-".format(max_depth)
    elif direction == "backward":
        rel_pattern = "-[:CITES*1..{}]->".format(max_depth)
    else:  # both
        rel_pattern = "-[:CITES*1..{}]-".format(max_depth)

    return_items = (
        ["related.nodeId AS nodeId"]
        + [f"related.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    query = f"""
    MATCH path = (paper:Paper {{nodeId: $paper_node_id}}){rel_pattern}(related:Paper)
    WHERE paper <> related
    WITH DISTINCT related, MIN(LENGTH(path)) AS depth
    RETURN {return_clause}, depth
    ORDER BY depth ASC, related.citationCount DESC
    LIMIT $limit
    """

    result = tx.run(query, paper_node_id=paper_node_id, limit=limit)

    records = []
    for record in result:
        paper_data = {"nodeId": record["nodeId"]}
        paper_data.update({prop: record[prop] for prop in return_properties})
        paper_data["depth"] = record["depth"]
        paper_data["path_length"] = record["depth"]  # Alias for clarity
        records.append(paper_data)

    return records
