from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag import driver as driver_module
from rag.tools import shared_models
from rag.tools.shared_models import PaperQueryParamsWithDates

CATEGORY_NODE_ID = Field(
    description=(
        "Unique node identifier (nodeId) for the category, as returned by search_nodes. "
        "This is the stable URI identifier for the category node."
    )
)
METHOD_NODE_ID = Field(
    description=(
        "Unique node identifier (nodeId) for the method, as returned by search_nodes. "
        "This is the stable URI identifier for the method node."
    )
)
METHOD_RETURN_PROPERTIES = Field(
    default=["name", "description", "introducedYear", "numberPapers"],
    description=(
        "Properties to return for each method. "
        "Available: name, description, introducedYear, numberPapers"
    )
)


class MethodPapersInput(PaperQueryParamsWithDates):
    """Input schema for finding papers that use a specific method."""
    method_node_id: str = METHOD_NODE_ID


@tool(args_schema=MethodPapersInput)
def method_papers(
    method_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
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
    order_by: Optional[str] = "date_desc",
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

    if order_by == "date_desc":
        order_clause = "paper.date DESC"
    elif order_by == "date_asc":
        order_clause = "paper.date ASC"
    else:
        order_clause = "paper.citationCount DESC"

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


class PaperMethodsInput(BaseModel):
    """Input schema for finding methods used in a paper."""
    paper_node_id: str = shared_models.PAPER_NODE_ID
    return_properties: List[str] = METHOD_RETURN_PROPERTIES


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


class TaskPapersInput(PaperQueryParamsWithDates):
    """Input schema for finding papers that address a specific task."""
    task_node_id: str = Field(
        description=(
            "Unique node identifier (nodeId) for the task, as returned by search_nodes. "
            "This is the stable URI identifier for the task node."
        )
    )


@tool(args_schema=TaskPapersInput)
def task_papers(
    task_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all papers that address a specific task.

    Traversal pattern: Task <- HAS_TASK <- Paper

    Use this when you need to:
    - Find papers working on a specific problem (e.g., "Image Classification", "Machine Translation")
    - Explore solutions for a task
    - Track progress on a task over time

    Returns:
        List of papers with nodeId, requested properties, ordered by date or citation count.
        Empty list if task not found or has no papers.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _task_papers_tx,
                task_node_id,
                limit,
                return_properties,
                order_by,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve task papers"}]


def _task_papers_tx(
    tx,
    task_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "task_node_id": task_node_id,
        "limit": limit,
    }

    return_items = (
        ["paper.nodeId AS nodeId"]
        + [f"paper.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    where_conditions = ["task.nodeId = $task_node_id"]
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
    MATCH (task:Task)<-[:HAS_TASK]-(paper:Paper)
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


class PaperTasksInput(BaseModel):
    """Input schema for finding tasks addressed in a paper."""
    paper_node_id: str = shared_models.PAPER_NODE_ID
    return_properties: List[str] = Field(
        default=["name", "description"],
        description="Properties to return for each task. Available: name, description"
    )


@tool(args_schema=PaperTasksInput)
def paper_tasks(
    paper_node_id: str,
    return_properties: List[str]
) -> List[Dict[str, Any]]:
    """
    Find all tasks addressed in a specific paper.

    Traversal pattern: Paper -> HAS_TASK -> Task

    Use this when you need to:
    - Identify problems addressed in a paper
    - Compare tasks across papers
    - Understand the application domain of a paper

    Returns:
        List of tasks with nodeId and requested properties.
        Empty list if paper not found or has no tasks.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _paper_tasks_tx,
                paper_node_id,
                return_properties
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve paper tasks"}]


def _paper_tasks_tx(tx, paper_node_id: str, return_properties: List[str]):
    """Transaction function for paper_tasks traversal."""
    return_items = (
        ["task.nodeId AS nodeId"]
        + [f"task.{prop} AS {prop}" for prop in return_properties]
    )
    return_clause = ", ".join(return_items)

    query = f"""
    MATCH (paper:Paper {{nodeId: $paper_node_id}})-[:HAS_TASK]->(task:Task)
    RETURN {return_clause}
    """

    result = tx.run(query, paper_node_id=paper_node_id)

    records = []
    for record in result:
        task_data = {"nodeId": record["nodeId"]}
        task_data.update({prop: record[prop] for prop in return_properties})
        records.append(task_data)

    return records


class CategoryPapersInput(PaperQueryParamsWithDates):
    """Input schema for finding papers in a research category."""
    category_node_id: str = CATEGORY_NODE_ID


@tool(args_schema=CategoryPapersInput)
def category_papers(
    category_node_id: str,
    limit: int,
    return_properties: List[str],
    order_by: Optional[str] = "date_desc",
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
    order_by: Optional[str] = "date_desc",
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

    if order_by == "date_desc":
        order_clause = "paper.date DESC"
    elif order_by == "date_asc":
        order_clause = "paper.date ASC"
    else:
        order_clause = "paper.citationCount DESC"

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


class CategoryMethodsInput(BaseModel):
    """Input schema for finding methods used in papers from a research category."""
    category_node_id: str = CATEGORY_NODE_ID
    return_properties: List[str] = METHOD_RETURN_PROPERTIES
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of methods to return"
    )
    min_papers_in_category: int = Field(
        default=1,
        ge=1,
        description="Minimum number of papers in THIS category that must use the method"
    )
    order_by: Literal["usage_count", "introducedYear"] = Field(
        default="usage_count",
        description=(
            "Sort by: usage_count (papers in category using method, descending), "
            "or introducedYear (newest first)"
        )
    )
    date_from: Optional[str] = shared_models.DATE_FROM
    date_to: Optional[str] = shared_models.DATE_TO


@tool(args_schema=CategoryMethodsInput)
def category_methods(
    category_node_id: str,
    return_properties: List[str],
    limit: int,
    min_papers_in_category: int = 1,
    order_by: str = "usage_count",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find methods used in papers from a specific research category.

    Traversal pattern: Category <- [:CATEGORY|MAIN_CATEGORY] <- Method <- HAS_METHOD <- Paper

    Use this when you need to:
    - Discover what techniques are popular in a research area
    - Compare method usage across categories
    - Find dominant methods in a field during a time period
    - Identify emerging techniques in a category

    Returns:
        List of methods with nodeId, requested properties, and papers_in_category 
        (number of papers in this category using the method, respecting date filters).
        Note: method.numberPapers shows total papers across ALL categories.
        Ordered by papers_in_category, introducedYear, or name.
        Empty list if category not found or has no methods meeting criteria.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _category_methods_tx,
                category_node_id,
                return_properties,
                limit,
                min_papers_in_category,
                order_by,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve category methods"}]


def _category_methods_tx(
    tx,
    category_node_id: str,
    return_properties: List[str],
    limit: int,
    min_papers_in_category: int = 1,
    order_by: str = "usage_count",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "category_node_id": category_node_id,
        "limit": limit,
        "min_papers": min_papers_in_category,
    }

    return_items = (
        ["method.nodeId AS nodeId"]
        + [f"method.{prop} AS {prop}" for prop in return_properties]
        + ["papers_in_category"]
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

    # order clause mapping
    if order_by == "usage_count":
        order_clause = "papers_in_category DESC, method.name ASC"
    elif order_by == "introducedYear":
        order_clause = "method.introducedYear DESC, method.name ASC"
    else:
        raise ValueError(f"Unknown order_by value {order_by}")

    # Note: Counting papers per method for a given category contains a subtlety due to
    # the graph structure:
    #
    # - Papers are never directly assigned to categories; they are connected to
    #   categories only via the methods they implement.
    # - This query returns all methods linked to the given category. For each method,
    #   it counts the number of papers that implement that method **and are connected
    #   to the category via the method itself**.
    #
    # This means:
    # - Every paper implementing a method will be counted for each category that the
    #   method belongs to.
    # - Methods linked to multiple categories can appear to have high usage counts in a
    #   category even if most papers are actually about another category.
    # - For example, in the 'Language Models' category, 'Diffusion' may appear as the
    #   most-used method, even though in practice most diffusion papers are about image
    #   generation. This occurs because the 'Diffusion' method node is linked to both
    #   categories, so every paper implementing it is counted under both.
    #
    # This is not a bug; it reflects the semantics of the current graph structure.
    query = f"""
    MATCH (category:Category)<-[:CATEGORY|MAIN_CATEGORY]-(method:Method)<-[:HAS_METHOD]-(paper:Paper)
    {where_clause}
    WITH method, COUNT(DISTINCT paper) AS papers_in_category
    WHERE papers_in_category >= $min_papers
    RETURN {return_clause}
    ORDER BY {order_clause}
    LIMIT $limit
    """

    result = tx.run(query, **params)

    records = []
    for record in result:
        method_data = {"nodeId": record["nodeId"]}
        method_data.update({prop: record[prop] for prop in return_properties})
        method_data["papers_in_category"] = record["papers_in_category"]
        records.append(method_data)

    return records


class MethodCategoriesInput(BaseModel):
    """Input schema for finding research categories where a method is used."""
    method_node_id: str = METHOD_NODE_ID
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of categories to return"
    )
    min_papers: int = Field(
        default=1,
        ge=1,
        description="Minimum number of papers in a category that must use this method"
    )
    date_from: Optional[str] = shared_models.DATE_FROM
    date_to: Optional[str] = shared_models.DATE_TO


@tool(args_schema=MethodCategoriesInput)
def method_categories(
    method_node_id: str,
    limit: int,
    min_papers: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find research categories where a specific method is used.

    Traversal pattern: Method -[:CATEGORY|MAIN_CATEGORY]-> Category
    Then count: Method <- HAS_METHOD <- Paper (filtered)

    Use this when you need to:
    - Identify research areas where a technique is applied
    - Track cross-domain adoption of a method
    - Discover unexpected applications of a technique
    - Understand the reach of a method across fields

    Returns:
        List of categories with nodeId, name, and papers_in_category
        (number of papers in that category using the method, respecting date filters).
        Ordered by papers_in_category descending (most used categories first).
        Empty list if method not found or has no categories meeting criteria.
    """
    driver = driver_module.get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.execute_read(
                _method_categories_tx,
                method_node_id,
                limit,
                min_papers,
                date_from,
                date_to,
            )
            return result
    except Exception as e:
        return [{"error": str(e), "message": "Failed to retrieve method categories"}]


def _method_categories_tx(
    tx,
    method_node_id: str,
    return_properties: List[str],
    limit: int,
    min_papers: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    params = {
        "method_node_id": method_node_id,
        "limit": limit,
        "min_papers": min_papers,
    }

    where_conditions = ["method.nodeId = $method_node_id"]
    if date_from:
        where_conditions.append("paper.date >= $date_from")
        params["date_from"] = date_from
    if date_to:
        where_conditions.append("paper.date <= $date_to")
        params["date_to"] = date_to

    where_clause = "WHERE " + " AND ".join(where_conditions)

    # Note: Counting papers per category for a given method contains a subtlety due to
    # the graph structure:
    #
    # - Papers are never directly assigned to categories; they are connected to
    #   categories only via the methods they implement.
    # - For a given method M, this query returns all categories that M is assigned to.
    #   For each category, it counts the number of papers that implement M **and are
    #   connected to that category via M itself**.
    #
    # This means:
    # - Every paper implementing M will be counted for each category that M belongs to.
    # - If M is linked to multiple categories, the same paper can appear in the count
    #   for multiple categories.
    # - As a result, seemingly unintuitive results can occur, e.g., the number of papers
    #   implementing 'Diffusion' can be identical for both Image Generation and Language
    #   Models, even though in practice most diffusion papers are about image generation.
    #
    # This is not a bug; it simply reflects the current semantics of category membership
    # in the graph.
    query = f"""
    MATCH (method:Method)<-[:HAS_METHOD]-(paper:Paper),
          (method)-[:CATEGORY|MAIN_CATEGORY]->(category:Category)
    {where_clause}
    WITH category, COUNT(DISTINCT paper) AS papers_in_category
    WHERE papers_in_category >= $min_papers
    RETURN 
        category.nodeId AS nodeId,
        category.name AS name,
        papers_in_category
    ORDER BY papers_in_category DESC, category.name ASC
    LIMIT $limit
    """

    result = tx.run(query, **params)

    records = []
    for record in result:
        category_data = {"nodeId": record["nodeId"]}
        category_data.update({prop: record[prop] for prop in return_properties})
        category_data["papers_in_category"] = record["papers_in_category"]
        records.append(category_data)

    return records
