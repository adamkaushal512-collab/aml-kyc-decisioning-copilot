from typing import Literal, Optional

from pydantic import BaseModel


class Case(BaseModel):
    case_id: str
    customer_name: str
    customer_id: str
    transaction_amount: Optional[float] = None
    transaction_type: Optional[str] = None
    case_type: Literal["kyc_refresh", "transaction_alert"]
    status: Literal["open", "under_review", "escalated", "cleared", "closed"] = "open"
