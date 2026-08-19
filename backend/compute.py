import math
import difflib
from typing import List, Dict, Optional, Any
from backend.models import (
    ReceiptData,
    DescriptionData,
    SplitResult,
    PersonShare,
    ReconciliationDetail,
    SettleUpTransaction
)
from backend.cross_check import cross_check_extraction_and_parsing


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation and extra whitespace for comparison."""
    import re
    return re.sub(r"[^a-z0-9\s]", "", s.strip().lower())


def _match_item_assignment(item_name: str, assignments: list) -> Optional[Any]:
    """Matches a receipt item name to an assignment using multi-strategy fuzzy matching.
    
    Strategies (in order):
    1. Exact normalized match
    2. One string is a substring of the other (e.g. 'Chicken Tikka' in 'Chicken Tikka Starter')
    3. difflib SequenceMatcher ratio >= 0.72 (handles typos, abbreviations, word order)
    
    Returns the best match or None.
    """
    norm_item = _normalize(item_name)
    best_match = None
    best_ratio = 0.0

    for assignment in assignments:
        norm_assign = _normalize(assignment.item_name)

        # Strategy 1: exact normalized match
        if norm_item == norm_assign:
            return assignment

        # Strategy 2: substring containment (handles partial names like "Naan" vs "Garlic Naan")
        if norm_assign in norm_item or norm_item in norm_assign:
            ratio = len(min(norm_item, norm_assign, key=len)) / max(len(norm_item), len(norm_assign), 1)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = assignment

        # Strategy 3: fuzzy similarity
        ratio = difflib.SequenceMatcher(None, norm_item, norm_assign).ratio()
        if ratio >= 0.72 and ratio > best_ratio:
            best_ratio = ratio
            best_match = assignment

    return best_match



def _is_item_ignored(item_name: str, ignored_items: List[str]) -> bool:
    """Fuzzy checks if a receipt item name matches any string in ignored_items."""
    norm_item = _normalize(item_name)
    for ig in ignored_items:
        norm_ig = _normalize(ig)
        if norm_item == norm_ig or norm_ig in norm_item or norm_item in norm_ig:
            return True
        if difflib.SequenceMatcher(None, norm_item, norm_ig).ratio() >= 0.72:
            return True
    return False

def compute_split(
    receipt: ReceiptData,
    description: DescriptionData
) -> SplitResult:
    """Computes deterministic, proportional itemized bill split and settle-up transactions.
    
    Rules applied:
    1. Individual items assigned 100% to the single consumer.
    2. Shared items split equally among specific consumers (per-item).
    3. Tax and service charge allocated proportional to each person's pre-tax food subtotal.
    4. Bill-level discount allocated proportional to each person's subtotal.
    5. Round to nearest rupee; leftover paisa diff absorbed by payer if present.
    6. Edge cases: missing payer, unmatched mentions, unclear references forwarded to flags.
    7. Anti-hallucination cross-check and confidence scoring.
    """
    flags: List[str] = []
    assumptions: List[str] = []

    # 0. Check for complete receipt mismatch
    if description.is_receipt_completely_wrong:
        raise ValueError("The provided receipt does not match the description at all. Please upload the correct receipt.")

    # 1. Forward flags and assumptions from prior pipeline stages
    if receipt.extraction_flags:
        flags.extend(receipt.extraction_flags)
    for um in description.unmatched_mentions:
        flags.append(f"Unmatched mention from description: '{um}'")
    for ur in description.unclear_references:
        flags.append(f"Unclear reference from description: '{ur}'")
    if description.parsing_assumptions:
        assumptions.extend(description.parsing_assumptions)

    # 2. Run bidirectional cross-check between receipt items and description assignments
    cross_check_flags = cross_check_extraction_and_parsing(receipt, description)
    for ccf in cross_check_flags:
        if ccf not in flags:
            flags.append(ccf)

    # 3. Resolve distinct group members
    people: List[str] = list(description.people)
    if not people:
        # Fallback: extract unique names from item_assignments
        inferred_names = set()
        for assign in description.item_assignments:
            inferred_names.update(assign.consumed_by)
        people = list(inferred_names) if inferred_names else ["Guest"]
        assumptions.append(f"People list inferred from item assignments: {people}")

    # 4. Allocate line items to consumers
    person_items_map: Dict[str, List[PersonItem]] = {p: [] for p in people}
    person_subtotals: Dict[str, float] = {p: 0.0 for p in people}
    
    deducted_ignored_amount = 0.0

    for item in receipt.items:
        if description.ignored_items and _is_item_ignored(item.name, description.ignored_items):
            deducted_ignored_amount += item.amount
            assumptions.append(f"Excluded '{item.name}' (₹{item.amount:.2f}) based on description overrides.")
            continue

        assignment = _match_item_assignment(item.name, description.item_assignments)
        if assignment and assignment.consumed_by:
            # Filter consumers that exist in group
            consumers = [c for c in assignment.consumed_by if c in people]
            if not consumers:
                consumers = assignment.consumed_by
                for c in consumers:
                    if c not in person_items_map:
                        person_items_map[c] = []
                        person_subtotals[c] = 0.0
                        people.append(c)
        else:
            # Not explicitly assigned -> fallback to shared among all known people
            consumers = people
            # Already flagged by cross_check_extraction_and_parsing if missing

        num_consumers = len(consumers)
        is_shared = num_consumers > 1
        split_amount = item.amount / num_consumers

        for c in consumers:
            person_items_map[c].append(item.name)
            person_subtotals[c] += split_amount

    # 5. Proportional Tax, Service Charge, Discount, and Round-Off Allocation
    grand_subtotal = sum(person_subtotals.values())
    if grand_subtotal <= 0:
        grand_subtotal = receipt.subtotal or receipt.grand_total or 1.0

    # Determine total tax
    total_tax = 0.0
    if description.tax_override is not None:
        total_tax = description.tax_override
        assumptions.append(f"Tax explicitly overridden to ₹{total_tax:.2f} based on description.")
    elif receipt.tax:
        if receipt.tax.total_tax is not None:
            total_tax = receipt.tax.total_tax
        else:
            total_tax = (receipt.tax.cgst or 0.0) + (receipt.tax.sgst or 0.0)

    total_service = receipt.service_charge or 0.0
    total_discount = receipt.discount.amount if receipt.discount else 0.0
    total_round_off = receipt.round_off or 0.0

    per_person_data: List[Dict[str, Any]] = []

    raw_totals: List[float] = []
    for p in people:
        sub = person_subtotals[p]
        proportion = sub / grand_subtotal if grand_subtotal > 0 else (1.0 / len(people))

        tax_share = int(round(proportion * total_tax))
        service_share = int(round(proportion * total_service))
        discount_share = int(round(proportion * total_discount))
        round_off_share = proportion * total_round_off

        raw_total = sub + (proportion * total_tax) + (proportion * total_service) - (proportion * total_discount) + round_off_share
        raw_totals.append(raw_total)

        per_person_data.append({
            "name": p,
            "items": person_items_map[p],
            "subtotal": int(round(sub)),
            "tax_share": tax_share,
            "service_share": service_share,
            "discount_share": discount_share,
            "raw_total": raw_total,
            "total": 0  # Filled in by LRM below
        })

    # 6. Largest Remainder Method (LRM) Rounding
    # Guarantees that integer-rounded person totals always sum to exactly grand_total (minus ignored items).
    adjusted_grand_total = max(0.0, receipt.grand_total - deducted_ignored_amount)
    target_int = int(round(adjusted_grand_total))
    floor_totals = [int(raw) for raw in raw_totals]
    remainders = [(raw - int(raw), i) for i, raw in enumerate(raw_totals)]
    deficit = target_int - sum(floor_totals)

    # Sort by remainder descending; give extra rupee to top `deficit` people
    remainders.sort(key=lambda x: x[0], reverse=True)
    lrm_totals = floor_totals[:]
    for k in range(max(0, int(deficit))):
        if k < len(remainders):
            lrm_totals[remainders[k][1]] += 1

    for i, p in enumerate(per_person_data):
        p["total"] = int(lrm_totals[i])

    # 6b. Reconciliation check after LRM — should be exact; flag if not
    sum_lrm = sum(p["total"] for p in per_person_data)
    lrm_diff = target_int - sum_lrm

    payer_name = description.payer
    payer_matched = False

    if payer_name:
        for p in per_person_data:
            if p["name"].strip().lower() == payer_name.strip().lower():
                payer_matched = True
                if lrm_diff != 0:
                    # LRM should have handled this; absorb any integer residual
                    p["total"] = int(p["total"] + lrm_diff)
                break

    if not payer_name or not payer_matched:
        if lrm_diff != 0:
            flags.append(
                f"Rounding residual of ₹{lrm_diff:+d} remains after LRM; "
                f"sum of person totals is ₹{sum_lrm} vs bill adjusted grand total ₹{target_int}."
            )


    # 7. Reconciliation Validation
    # We must match against the adjusted grand total
    per_person_final = [PersonShare(**p) for p in per_person_data]

    final_sum_totals = sum(p.total for p in per_person_final)
    matches_bill = (final_sum_totals == target_int)

    if not matches_bill:
        flags.append(
            f"Reconciliation mismatch: sum of person totals (₹{final_sum_totals}) "
            f"does not match adjusted grand total (₹{target_int})."
        )

    reconciliation = ReconciliationDetail(
        sum_of_person_totals=int(final_sum_totals),
        matches_bill=matches_bill
    )

    # 8. Settle-Up Calculations
    settle_up: List[SettleUpTransaction] = []
    resolved_paid_by: Optional[str] = None

    if payer_name and payer_matched:
        # Find exact casing of payer
        actual_payer_name = next(p.name for p in per_person_final if p.name.strip().lower() == payer_name.strip().lower())
        resolved_paid_by = actual_payer_name
        for p in per_person_final:
            if p.name != actual_payer_name and p.total > 0:
                settle_up.append(
                    SettleUpTransaction(
                        from_person=p.name,
                        to_person=actual_payer_name,
                        amount=int(p.total)
                    )
                )
        assumptions.append(
            f"Direct-to-payer settle-up transactions generated: each non-payer reimburses {actual_payer_name} directly."
        )
    else:
        flags.append("Payer not specified in description. Settle-up transactions cannot be computed.")

    return SplitResult(
        per_person=per_person_final,
        grand_total=int(round(receipt.grand_total)),
        reconciliation=reconciliation,
        paid_by=resolved_paid_by,
        settle_up=settle_up,
        assumptions=assumptions,
        flags=flags
    )

