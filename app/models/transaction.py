from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    Date: str = Field(..., pattern=r"^\d{2}/\d{2}/\d{2}$")
    Description: str
    Category: str
    Expenditure: float = Field(..., gt=0)
    Year: int
    Month: int = Field(..., ge=1, le=12)
    Day: int = Field(..., ge=1, le=31)


class TransactionResponse(BaseModel):
    id: int
    Date: str
    Description: str
    Category: str
    Expenditure: float
    Year: int
    Month: int
    Day: int
