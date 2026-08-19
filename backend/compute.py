import math
import difflib
from typing import List, Dict, Optional, Any
from backend.models import (
    ReceiptData,
    DescriptionData,
    SplitResult,
    PersonShare,
    PersonItem,
    ReconciliationDetail,
    SettleUpTransaction,
    ConfidenceDetail
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

    for item in receipt.items:
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
            person_items_map[c].append(
                PersonItem(
                    name=item.name,
                    amount=round(split_amount, 2),
                    is_shared=is_shared
                )
            )
            person_subtotals[c] += split_amount

    # 5. Proportional Tax, Service Charge, Discount, and Round-Off Allocation
    grand_subtotal = sum(person_subtotals.values())
    if grand_subtotal <= 0:
        grand_subtotal = receipt.subtotal or receipt.grand_total or 1.0

    # Determine total tax
    total_tax = 0.0
    if receipt.tax:
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

        tax_share = round(proportion * total_tax, 2)
        service_share = round(proportion * total_service, 2)
        discount_share = round(proportion * total_discount, 2)
        round_off_share = proportion * total_round_off

        raw_total = sub + (proportion * total_tax) + (proportion * total_service) - (proportion * total_discount) + round_off_share
        raw_totals.append(raw_total)

        per_person_data.append({
            "name": p,
            "items": person_items_map[p],
            "subtotal": round(sub, 2),
            "tax_share": tax_share,
            "service_share": service_share,
            "discount_share": discount_share,
            "raw_total": raw_total,
            "total": 0.0  # Filled in by LRM below
        })

    # 6. Largest Remainder Method (LRM) Rounding
    # Guarantees that integer-rounded person totals always sum to exactly grand_total.
    # Standard Python round() can accumulate ±N/2 rupees of error for N people.
    # LRM: floor everyone, then give 1 extra rupee to the N people with the largest remainders.
    target_int = int(round(receipt.grand_total))
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
        p["total"] = float(lrm_totals[i])

    # 6b. Reconciliation check after LRM \u2014 should be exact; flag if not
    sum_lrm = sum(p["total"] for p in per_person_data)
    lrm_diff = round(receipt.grand_total - sum_lrm, 2)

    payer_name = description.payer
    payer_matched = False

    if payer_name:
        for p in per_person_data:
            if p["name"].strip().lower() == payer_name.strip().lower():
                payer_matched = True
                if abs(lrm_diff) > 0.001:
                    # LRM should have handled this; absorb any floating-point residual
                    p["total"] = float(round(p["total"] + lrm_diff))
                break

    if not payer_name or not payer_matched:
        if abs(lrm_diff) > 0.001:
            flags.append(
                f"Rounding residual of ₹{lrm_diff:+.2f} remains after LRM; "
                f"sum of person totals is ₹{sum_lrm:.2f} vs bill grand total ₹{receipt.grand_total:.2f}."
            )


    # 7. Final PersonShare Construction & Reconciliation
    per_person_final: List[PersonShare] = []
    for p in per_person_data:
        per_person_final.append(
            PersonShare(
                name=p["name"],
                items=p["items"],
                subtotal=p["subtotal"],
                tax_share=p["tax_share"],
                service_share=p["service_share"],
                discount_share=p["discount_share"],
                total=p["total"]
            )
        )

    final_sum_totals = sum(p.total for p in per_person_final)
    matches_bill = abs(final_sum_totals - receipt.grand_total) <= 2.0

    if not matches_bill:
        flags.append(
            f"Reconciliation mismatch: sum of person totals (₹{final_sum_totals:.2f}) "
            f"does not match grand total (₹{receipt.grand_total:.2f}) within ₹2.00 tolerance."
        )

    reconciliation = ReconciliationDetail(
        sum_of_person_totals=final_sum_totals,
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
                        amount=p.total
                    )
                )
        assumptions.append(
            f"Direct-to-payer settle-up transactions generated: each non-payer reimburses {actual_payer_name} directly."
        )
    else:
        flags.append("Payer not specified in description. Settle-up transactions cannot be computed.")

    # 9. Anti-Hallucination Confidence Assessment
    confidence_reasons: List[str] = []
    
    # Include all flags
    if flags:
        confidence_reasons.extend(flags)
        
    # Check fallback providers used
    if getattr(receipt, "used_fallback", False):
        fb_reason = getattr(receipt, "fallback_reason", None)
        if fb_reason == "timeout":
            confidence_reasons.append("Vision OCR extraction: Gemini timed out after 15s, falling back to OpenRouter.")
        elif fb_reason == "rate_limit_429":
            confidence_reasons.append("Vision OCR extraction: Gemini returned 429 rate limit, falling back to OpenRouter.")
        else:
            confidence_reasons.append("Vision OCR extraction utilized fallback model instead of primary provider.")

    if getattr(description, "used_fallback", False):
        fb_reason = getattr(description, "fallback_reason", None)
        if fb_reason == "timeout":
            confidence_reasons.append("Description parsing: Groq timed out after 10s, falling back to OpenRouter.")
        elif fb_reason == "rate_limit_429":
            confidence_reasons.append("Description parsing: Groq returned 429 rate limit, falling back to OpenRouter.")
        else:
            confidence_reasons.append("Description parsing utilized fallback model instead of primary provider.")
        
    # Check unmatched mentions or unclear references
    for um in description.unmatched_mentions:
        if f"Unmatched mention from description: '{um}'" not in confidence_reasons:
            confidence_reasons.append(f"Unmatched mention from description: '{um}'")
    for ur in description.unclear_references:
        if f"Unclear reference from description: '{ur}'" not in confidence_reasons:
            confidence_reasons.append(f"Unclear reference from description: '{ur}'")

    # Deduplicate reasons while preserving order
    deduped_reasons = list(dict.fromkeys(confidence_reasons))

    if not deduped_reasons:
        confidence = ConfidenceDetail(level="high", reasons=[])
    else:
        confidence = ConfidenceDetail(level="needs_review", reasons=deduped_reasons)

    return SplitResult(
        per_person=per_person_final,
        grand_total=receipt.grand_total,
        reconciliation=reconciliation,
        paid_by=resolved_paid_by,
        settle_up=settle_up,
        assumptions=assumptions,
        flags=flags,
        confidence=confidence
    )

