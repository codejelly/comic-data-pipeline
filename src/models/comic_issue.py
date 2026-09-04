from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class ComicIssueSchema(BaseModel):
    locg_issue_id: int
    parent_id: int
    main_title: str
    publisher: str
    assigned_tier: str
    cover_info: Optional[str] = None
    retail_price: Optional[float] = Field(default=None, ge=0)
    image_url: Optional[HttpUrl] = None
    current_pull_count: int = Field(default=0, ge=0)
    days_to_street_date: Optional[int] = None
    street_date: Optional[str] = None  # Accepts "YYYY-MM-DD" or None
