from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module
from rag.tools import shared_models
from rag.tools.shared_models import PaperQueryParamsWithDates


class MethodPapersInput(PaperQueryParamsWithDates):
    """Input schema for finding papers that use a specific method."""
    method_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the method, as returned by search_nodes. "
            "This is the stable URI identifier for the method node."
        )
    )


@tool(args_schema=MethodPapersInput)
def method_papers(
    method_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all papers that use a specific method.

    Traversal pattern: Method <- HAS_METHOD <- Paper

    Use this when you need to:
    - Find papers implementing a specific technique (e.g., "LSTM", "ResNet")
    - Explore applications of a method
    - Track adoption of a technique over time

    Returns:
        List of papers with nodeId, requested properties, ordered by date or citation count.
        Empty list if method not found or has no papers.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _method_papers_tx,
                method_node_id,
                limit,
                return_properties,
                order_by,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve method papers"}]


def _method_papers_tx(
    tx,
    method_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "method_node_id": method_node_id,
        "limit": limit,
    }

    return_items = (
        ["paper.nodeId AS nodeId"]
        + [f"paper.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    where_conditions = ["method.nodeId = $method_node_id"]
    if date_from:
        where_conditions.append("paper.date >= $date_from")
        params["date_from"] = date_from
    if date_to:
        where_conditions.append("paper.date <= $date_to")
        params["date_to"] = date_to

    where_clause = "WHERE " + " AND ".join(where_conditions)

    order_clause = (
        "paper.date DESC" if order_by == "date" else "paper.citationCount DESC"
    )

    query = f"""
    MATCH (method:Method)<-[:HAS_METHOD]-(paper:Paper)
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


class CategoryPapersInput(PaperQueryParamsWithDates):
    """Input schema for finding papers in a research category."""
    category_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the category, as returned by search_nodes. "
            "This is the stable URI identifier for the category node."
        )
    )


@tool(args_schema=CategoryPapersInput)
def category_papers(
    category_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all papers in a specific research category.

    Traversal pattern: Category <- [:CATEGORY|MAIN_CATEGORY] <- Method <- HAS_METHOD <- Paper

    Use this when you need to:
    - Explore papers in a broad research area (e.g., "Image Generation Models", "Optimization")
    - Find recent work in a field
    - Get an overview of a research domain

    Returns:
        List of papers with nodeId, requested properties, ordered by date or citation count.
        Empty list if category not found or has no papers.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _category_papers_tx,
                category_node_id,
                limit,
                return_properties,
                order_by,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve category papers"}]


def _category_papers_tx(
    tx,
    category_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "category_node_id": category_node_id,
        "limit": limit,
    }

    return_items = (
        ["paper.nodeId AS nodeId"]
        + [f"paper.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    where_conditions = ["category.nodeId = $category_node_id"]
    
    if date_from:
        where_conditions.append("paper.date >= $date_from")
        params["date_from"] = date_from
    
    if date_to:
        where_conditions.append("paper.date <= $date_to")
        params["date_to"] = date_to
    
    where_clause = "WHERE " + " AND ".join(where_conditions)

    order_clause = (
        "paper.date DESC" if order_by == "date" else "paper.citationCount DESC"
    )

    query = f"""
    MATCH (category:Category)<-[:CATEGORY|MAIN_CATEGORY]-(method:Method)<-[:HAS_METHOD]-(paper:Paper)
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


class PaperMethodsInput(BaseModel):
    """Input schema for finding methods used in a paper."""
    paper_node_id: str = shared_models.PAPER_NODE_ID
    return_properties: List[str] = Field(
        default=["name", "description", "introducedYear", "numberPapers"],
        description=(
            "Properties to return for each method. "
            "Available: name, description, introducedYear, numberPapers"
        )
    )


@tool(args_schema=PaperMethodsInput)
def paper_methods(
    paper_node_id: str,
    return_properties: List[str]
) -> List[Dict[str, Any]]:
    """
    Find all methods used in a specific paper.

    Traversal pattern: Paper -> HAS_METHOD -> Method

    Use this when you need to:
    - Identify techniques used in a paper
    - Compare methods across papers
    - Understand the technical approach of a paper

    Returns:
        List of methods with nodeId and requested properties.
        Empty list if paper not found or has no methods.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_methods_tx,
                paper_node_id,
                return_properties
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve paper methods"}]


def _paper_methods_tx(tx, paper_node_id: str, return_properties: List[str]):
    """Transaction function for paper_methods traversal."""
    return_items = (
        ["method.nodeId AS nodeId"]
        + [f"method.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    query = f"""
    MATCH (paper:Paper {{nodeId: $paper_node_id}})-[:HAS_METHOD]->(method:Method)
    RETURN {return_clause}
    """

    result = tx.run(query, paper_node_id=paper_node_id)

    records = []
    for record in result:
        method_data = {"nodeId": record["nodeId"]}
        method_data.update({prop: record[prop] for prop in return_properties})
        records.append(method_data)

    return records
