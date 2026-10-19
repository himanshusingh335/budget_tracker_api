from typing import Literal, Optional

from pydantic import BaseModel, Field

EmailTransactionType = Literal["UPI", "Credit Card", "Debit Card", "Net Banking", "Other"]


class EmailTransactionCreate(BaseModel):
    Date: str = Field(..., pattern=r"^\d{2}/\d{2}/\d{2}$")
    Description: str
    Type: EmailTransactionType
    Amount: float = Field(..., description="Negative for debits, positive for credits")
    Account: Optional[str] = None
    Year: int
    Month: int = Field(..., ge=1, le=12)
    Day: int = Field(..., ge=1, le=31)
    MessageId: str = Field(..., min_length=1)
