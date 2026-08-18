import re
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator


def _parse_float(val: Any) -> Optional[float]:
    """Helper to convert string/int/float into clean float, handling currency and negative signs."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r"[^\d.-]", "", val.strip())
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


class ReceiptItem(BaseModel):
    name: str = Field(..., description="Name or description of the item")
    qty: float = Field(default=1.0, description="Quantity of the item")
    unit_price: float = Field(..., description="Price per unit of the item")
    amount: float = Field(..., description="Total price for this line item (qty * unit_price)")

    @field_validator("qty", "unit_price", "amount", mode="before")
    @classmethod
    def parse_numeric(cls, v: Any) -> float:
        parsed = _parse_float(v)
        return parsed if parsed is not None else 0.0


class DiscountDetail(BaseModel):
    amount: float = Field(..., description="Total discount amount deducted")
    label: Optional[str] = Field(None, description="Discount description or coupon name if specified")

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v: Any) -> float:
        parsed = _parse_float(v)
        # Store discount amount as positive magnitude
        return abs(parsed) if parsed is not None else 0.0


class TaxBreakdown(BaseModel):
    cgst: Optional[float] = Field(None, description="Central GST amount if shown")
    sgst: Optional[float] = Field(None, description="State GST amount if shown")
    total_tax: Optional[float] = Field(None, description="Total tax amount combined")

    @field_validator("cgst", "sgst", "total_tax", mode="before")
    @classmethod
    def parse_tax_floats(cls, v: Any) -> Optional[float]:
        return _parse_float(v)


class ReceiptData(BaseModel):
    restaurant_name: Optional[str] = Field(None, description="Name of the restaurant or establishment")
    bill_number: Optional[str] = Field(None, description="Invoice or bill identifier if present")
    items: List[ReceiptItem] = Field(default_factory=list, description="List of line items on the receipt")
    subtotal: Optional[float] = Field(None, description="Subtotal before taxes, discounts, or service charges")
    discount: Optional[DiscountDetail] = Field(None, description="Discount details if any")
    service_charge: Optional[float] = Field(None, description="Service charge or tip amount if any")
    tax: Optional[TaxBreakdown] = Field(None, description="Tax breakdown including CGST, SGST, or total tax")
    round_off: Optional[float] = Field(None, description="Round-off adjustment (+/-) if any")
    grand_total: float = Field(..., description="Final payable grand total")
    extraction_flags: List[str] = Field(default_factory=list, description="Quality and validation warning flags")

    @field_validator("subtotal", "service_charge", "round_off", "grand_total", mode="before")
    @classmethod
    def parse_optional_floats(cls, v: Any) -> Any:
        if v is None:
            return None
        parsed = _parse_float(v)
        return parsed if parsed is not None else v

    @field_validator("discount", mode="before")
    @classmethod
    def normalize_discount(cls, v: Any) -> Optional[DiscountDetail]:
        if v is None or v == "" or v == 0:
            return None
        if isinstance(v, (int, float, str)):
            amt = _parse_float(v)
            if amt is not None and abs(amt) > 0:
                return DiscountDetail(amount=abs(amt), label=None)
            return None
        if isinstance(v, dict):
            amt = _parse_float(v.get("amount"))
            if amt is not None and abs(amt) > 0:
                return DiscountDetail(amount=abs(amt), label=v.get("label"))
            return None
        return v

    @field_validator("tax", mode="before")
    @classmethod
    def normalize_tax(cls, v: Any) -> Optional[TaxBreakdown]:
        if v is None or v == "" or v == 0:
            return None
        if isinstance(v, (int, float, str)):
            amt = _parse_float(v)
            if amt is not None and amt > 0:
                return TaxBreakdown(total_tax=amt)
            return None
        if isinstance(v, dict):
            cgst = _parse_float(v.get("cgst"))
            sgst = _parse_float(v.get("sgst"))
            tot = _parse_float(v.get("total_tax"))
            if tot is None and (cgst is not None or sgst is not None):
                tot = (cgst or 0.0) + (sgst or 0.0)
            return TaxBreakdown(cgst=cgst, sgst=sgst, total_tax=tot)
        return v


class ItemAssignment(BaseModel):
    item_name: str = Field(..., description="Name of the item as identified from known_items or description")
    consumed_by: List[str] = Field(default_factory=list, description="List of person names who consumed/shared this item")
    is_shared: bool = Field(default=False, description="True if shared by multiple people, False if individual")


class DescriptionData(BaseModel):
    people: List[str] = Field(default_factory=list, description="List of all people in the dining group")
    payer: Optional[str] = Field(None, description="Name of the person who paid the bill, or null if not explicitly stated")
    item_assignments: List[ItemAssignment] = Field(default_factory=list, description="Mapping of line items to consumers")
    unmatched_mentions: List[str] = Field(
        default_factory=list,
        description="Items mentioned in description that do not match any known receipt item"
    )
    unclear_references: List[str] = Field(
        default_factory=list,
        description="Ambiguous phrases or unresolvable references in the description"
    )
    parsing_assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions or inferences made during parsing when details were implicit"
    )


class PersonItem(BaseModel):
    name: str = Field(..., description="Name of the consumed item")
    amount: float = Field(..., description="Individual share amount for this line item")
    is_shared: bool = Field(default=False, description="True if split among multiple people")


class PersonShare(BaseModel):
    name: str = Field(..., description="Person's name")
    items: List[PersonItem] = Field(default_factory=list, description="Items consumed by this person with split amount")
    subtotal: float = Field(..., description="Sum of individual item shares before tax/service/discount")
    tax_share: float = Field(..., description="Proportional share of GST / taxes")
    service_share: float = Field(..., description="Proportional share of service charge")
    discount_share: float = Field(..., description="Proportional share of discounts")
    total: float = Field(..., description="Final individual total amount payable (rounded to nearest rupee)")


class ReconciliationDetail(BaseModel):
    sum_of_person_totals: float = Field(..., description="Sum of all individual person totals")
    matches_bill: bool = Field(..., description="True if sum of person totals matches grand total within tolerance")


class SettleUpTransaction(BaseModel):
    from_person: str = Field(..., alias="from", description="Person who owes money")
    to_person: str = Field(..., alias="to", description="Person to be reimbursed (payer)")
    amount: float = Field(..., description="Amount to transfer (rounded to nearest rupee)")

    class Config:
        populate_by_name = True


class SplitResult(BaseModel):
    per_person: List[PersonShare] = Field(default_factory=list, description="Breakdown per person")
    grand_total: float = Field(..., description="Grand total from the receipt")
    reconciliation: ReconciliationDetail = Field(..., description="Reconciliation check against receipt total")
    paid_by: Optional[str] = Field(None, description="Payer name if specified")
    settle_up: List[SettleUpTransaction] = Field(default_factory=list, description="Settle-up transfer instructions")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions and rounding allocations made")
    flags: List[str] = Field(default_factory=list, description="Reconciliation or parsing warning flags")

    class Config:
        populate_by_name = True


class SplitRequest(BaseModel):
    receipt_base64: str = Field(..., description="Base64 encoded receipt image bytes (without data-URI prefix)")
    description: str = Field(..., description="Natural language description of group dining consumption")



