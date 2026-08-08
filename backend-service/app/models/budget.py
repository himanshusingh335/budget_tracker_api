from pydantic import BaseModel, Field, field_validator
import re


class BudgetCreate(BaseModel):
    MonthYear: str = Field(..., pattern=r"^\d{2}/\d{2}$")
    Category: str
    Budget: float = Field(..., gt=0)


class BudgetResponse(BaseModel):
    id: int
    MonthYear: str
    Category: str
    Budget: float


class BudgetDeleteRequest(BaseModel):
    MonthYear: str
    Category: str


class SummaryRow(BaseModel):
    MonthYear: str
    Category: str
    Budget: str
    Expenditure: str
    Difference: str
