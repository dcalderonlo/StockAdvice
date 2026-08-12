# classification-engine — Specification

## Purpose

Runs a periodic classification pass over the catalog to derive Volume Class (VC1–VC8) and Lifecycle Stage codes (New, Obsolete, Inactive, Special) from sales data. Classification drives replenishment behavior and is visible in the dashboard for gerente review.

## Requirements

### REQ-CE-001: Volume Class derivation
The system **shall** assign a Volume Class code based on annual sales volume per SKU:

| Code | Annual Sales |
|------|-------------|
| VC1 | > 250 |
| VC2 | 121–250 |
| VC3 | 61–120 |
| VC4 | 31–60 |
| VC5 | 15–30 |
| VC6 | 7–14 |
| VC7 | 4–6 |
| VC8 | 1–3 |

Zero annual sales returns no Volume Class (cold-start).

#### Scenario: Fast mover classification
- GIVEN a SKU with 300 annual sales
- WHEN the classification pass runs
- THEN the SKU is classified as VC1

#### Scenario: Boundary classification
- GIVEN a SKU with exactly 121 annual sales
- WHEN the classification pass runs
- THEN the SKU is classified as VC2 (not VC3)

#### Scenario: Zero sales — no classification
- GIVEN a SKU with 0 annual sales
- WHEN the classification pass runs
- THEN no Volume Class is assigned
- AND the SKU is flagged for cold-start handling

### REQ-CE-002: Lifecycle Stage — New
The system **shall** classify SKUs in their first 6 months from entry as New, with sub-codes:
- N1: > 15 sales in first 6 months (high velocity new)
- N2: 4–15 sales in first 6 months (moderate velocity new)
- N3: 0–3 sales in first 6 months (low velocity new)

#### Scenario: High-velocity new SKU
- GIVEN a SKU added 4 months ago with 18 sales in its first 6 months
- WHEN the classification pass runs
- THEN the SKU is classified as N1

#### Scenario: Low-velocity new SKU
- GIVEN a SKU added 2 months ago with 1 sale
- WHEN the classification pass runs
- THEN the SKU is classified as N3

### REQ-CE-003: Lifecycle Stage — Obsolete
The system **shall** classify SKUs as Obsolete based on time without sales:
- OBS-S: Replacement of old reference (successor exists)
- OBS-N: > 6 months in stock, never sold
- OBS-P: > 12 months without sales (pre-obsolescence)
- OBS-R: > 24 months without sales (full obsolescence)

#### Scenario: Pre-obsolescence flag
- GIVEN a SKU with no sales for 14 months and still in stock
- WHEN the classification pass runs
- THEN the SKU is classified as OBS-P
- AND the SKU remains eligible for recommendations (flagged for review)

#### Scenario: Full obsolescence
- GIVEN a SKU with no sales for 26 months
- WHEN the classification pass runs
- THEN the SKU is classified as OBS-R
- AND the SKU is excluded from automatic recommendations
- AND the SKU remains visible in the catalog for historical reference

#### Scenario: Never sold but in stock
- GIVEN a SKU in stock for 8 months with zero sales since entry
- WHEN the classification pass runs
- THEN the SKU is classified as OBS-N

### REQ-CE-004: Lifecycle Stage — Inactive
The system **shall** classify SKUs as Inactive when they have no sales for > 12 months AND no stock remaining.

#### Scenario: No sales, no stock
- GIVEN a SKU with no sales for 14 months and zero stock
- WHEN the classification pass runs
- THEN the SKU is classified as Inactive

### REQ-CE-005: Lifecycle Stage — Special
The system **shall** support special lifecycle codes that require gerente confirmation:
- NS-C: Campaign / Recall (linked to recall, special handling)
- NS-NS: Non-stock / Individual order (no auto-replenishment, ordered per request only)

#### Scenario: Campaign/recall flag
- GIVEN a SKU flagged by the DMS as part of a recall campaign
- WHEN the classification pass runs
- THEN the SKU is classified as NS-C
- AND the classification requires gerente confirmation before taking effect

#### Scenario: Non-stock individual order
- GIVEN a SKU marked as non-stock in the DMS
- WHEN the classification pass runs
- THEN the SKU is classified as NS-NS
- AND the SKU is excluded from automatic replenishment

### REQ-CE-006: Classification pass frequency
The system **shall** run the classification pass on a separate schedule (e.g., monthly) from the replenishment run. Volume Classes are applied automatically; Lifecycle Stage codes (except Volume Class) require gerente or delegated coordinator review and confirmation.

#### Scenario: Monthly classification pass
- GIVEN the classification pass is scheduled monthly
- WHEN the first day of the month arrives at the configured time
- THEN the system classifies all active SKUs
- AND Volume Classes are applied immediately
- AND Lifecycle Stage codes enter a review queue for gerente

#### Scenario: Gerente reviews classification
- GIVEN a classification pass produced 5 new Lifecycle Stage codes
- WHEN the gerente reviews the classification queue
- THEN the gerente can confirm or override each code
- AND confirmed codes take effect immediately

### REQ-CE-007: Cross-reference group classification
When evaluating a cross-reference group (equivalent parts from different manufacturers), the system **shall** apply the most conservative lifecycle stage across the group.

#### Scenario: Conservative lifecycle across equivalents
- GIVEN SKU-A is Active and SKU-B (equivalent) is OBS-P
- WHEN the system evaluates the cross-reference group
- THEN the group is treated as OBS-P for review purposes
- AND the more conservative classification drives the recommendation behavior

## Edge cases

- SKU with exactly 6 months since entry (boundary between New and Active)
- SKU with exactly 12 months without sales (OBS-P boundary)
- SKU with exactly 24 months without sales (OBS-R boundary)
- SKU reactivated after being classified as Inactive (new entry date resets clock)
- Cross-reference group with mixed lifecycle stages
- Classification pass runs during active replenishment run (idempotency)
- SKU deleted from DMS after classification (orphaned classification result)

## Acceptance criteria

- AC-1: Volume Class thresholds match the defined boundaries exactly (VC1 > 250, VC8 1–3)
- AC-2: Zero annual sales produces no Volume Class assignment
- AC-3: OBS-R SKUs are excluded from automatic recommendations
- AC-4: NS-NS SKUs are excluded from automatic replenishment
- AC-5: Classification pass runs independently of replenishment schedule
- AC-6: Cross-reference groups use the most conservative lifecycle stage

## Notes

- Classification pass is a separate scheduled job (monthly) per design.md §5
- Volume Classes are auto-applied; Lifecycle Stages require review
- Gerente may delegate classification review to a designated coordinator
