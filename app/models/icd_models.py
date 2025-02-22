from pydantic import BaseModel
from typing import Optional

class ICDCode(BaseModel):
    category_code: str  # A00, A010, etc.
    subcategory: Optional[str]  # 0, 1, 9, etc.
    full_code: str  # A000, A001, etc.
    short_description: str
    long_description: str
    category_name: str

class ICDResponse(BaseModel):
    code: str
    description: str
    category: str
    related_conditions: list[str]