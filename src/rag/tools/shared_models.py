from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PAPER_NODE_ID = Field(
    description=(
        "Unique node identifier (nodeId) for the paper, as returned by search_nodes. "
        "This is the stable URI identifier for the paper node."
    )
)
DATE_FROM = Field(
    default=None,
    description="Filter papers published after this date (YYYY-MM-DD or YYYY)"
)
DATE_TO = Field(
    default=None,
    description="Filter papers published before this date (YYYY-MM-DD or YYYY)"
)


class PaperQueryParams(BaseModel):
    """Common query parameters for paper search."""
    limit: int = Field(
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
    order_by: Optional[Literal["date_desc", "date_asc", "citationCount"]] = Field(
        default="date_desc",
        description=(
            "Sort by date_desc (newest first), date_asc (oldest_first), or citation "
            "count (highest first)"
        )
    )


class PaperQueryParamsWithDates(PaperQueryParams):
    """Common query parameters for paper search with date filers."""
    date_from: Optional[str] = DATE_FROM
    date_to: Optional[str] = DATE_TO
