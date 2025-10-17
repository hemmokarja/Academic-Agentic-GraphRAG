from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PAPER_NODE_ID = Field(
    description=(
        "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
        "This is the stable URI identifier for the paper node."
    )
)


class PaperQueryParams(BaseModel):
    """Common query parameters for paper search."""
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of papers to return"
    )
    return_properties: List[str] = Field(
        default=["title", "date", "citationCount"],
        description=(
            "Properties to return for each paper. "
            "Available: title, date, citationCount, abstract, hasURL, hasArXivId"
        )
    )
    order_by: Optional[Literal["date", "citationCount"]] = Field(
        default="date",
        description="Sort by date (newest first) or citation count (highest first)"
    )


class PaperQueryParamsWithDates(PaperQueryParams):
    """Common query parameters for paper search with date filers."""
    date_from: Optional[str] = Field(
        default=None,
        description="Filter papers published after this date (YYYY-MM-DD or YYYY)"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Filter papers published before this date (YYYY-MM-DD or YYYY)"
    )
