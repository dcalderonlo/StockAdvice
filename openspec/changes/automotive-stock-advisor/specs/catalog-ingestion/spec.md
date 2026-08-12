# catalog-ingestion — Specification

## Purpose

Reads catalog, stock, sales movements, lead times, Stock en Tránsito, cross-reference relationships, and branch topology from the DMS/ERP via a swappable adapter interface. The system consumes DMS data as-is (DMS is the source of truth) and never writes back. Supports distribution center topology and cross-OEM equivalent references.

## Requirements

### REQ-CI-001: Catalog read
The system **shall** read the parts catalog from the DMS, including:
- Internal SKU code (primary key)
- Primary manufacturer code
- Alternative manufacturer codes (1 Part ↔ N alternative manufacturer cross-reference)
- Description

#### Scenario: Successful catalog ingestion
- GIVEN a branch is configured with a DMS adapter
- WHEN the scheduled replenishment run triggers
- THEN the system reads the full parts catalog from the DMS
- AND persists the catalog data in its own database

#### Scenario: Empty catalog
- GIVEN a branch's DMS returns zero parts
- WHEN the system reads the catalog
- THEN the system records an empty catalog for that branch
- AND logs a warning that no SKUs are available for replenishment

#### Scenario: DMS adapter timeout
- GIVEN the DMS is unresponsive for more than 30 seconds
- WHEN the system attempts to read the catalog
- THEN the system retries up to 3 times with exponential backoff
- AND if all retries fail, logs an ERROR and alerts the operations team

### REQ-CI-002: Stock read
The system **shall** read live stock levels per branch warehouse, including Stock Disponible (physically available) and Stock en Tránsito (inbound units from any source).

#### Scenario: Stock read with transit
- GIVEN a branch has 15 units physically available and 10 units in transit
- WHEN the system reads stock levels
- THEN Stock Disponible = 15 and Stock en Tránsito = 10
- AND both values are stored as separate fields

#### Scenario: Missing SKU in stock table
- GIVEN a part exists in the catalog but has no stock record
- WHEN the system reads stock levels
- THEN the system treats Stock Disponible = 0 and Stock en Tránsito = 0 for that SKU
- AND flags the SKU as a cold-start candidate

#### Scenario: Zero stock
- GIVEN a SKU has no physical stock and no transit
- WHEN the system reads stock levels
- THEN Stock Disponible = 0 and Stock en Tránsito = 0
- AND the SKU is eligible for replenishment recommendation

### REQ-CI-003: Sales movements read
The system **shall** read sales movements from the DMS, including POS public sales (outbound), workshop consumption (outbound), and purchase entries (inbound), with at least 12 months of history.

#### Scenario: Full sales history import
- GIVEN a branch has 18 months of sales history in the DMS
- WHEN the system reads sales movements
- THEN the system imports all 18 months of data
- AND distinguishes between outbound (sales, workshop) and inbound (purchases) movements

#### Scenario: Insufficient history
- GIVEN a branch has only 6 months of sales history
- WHEN the system reads sales movements
- THEN the system imports the available 6 months
- AND flags the branch for limited classification accuracy

#### Scenario: No sales history
- GIVEN a newly activated branch with zero historical sales
- WHEN the system reads sales movements
- THEN the system records an empty sales history
- AND all SKUs for this branch are treated as cold-start

### REQ-CI-004: Lead time read
The system **shall** read lead times (Tiempo de Pedido) per supplier or per product, as available from the DMS or configuration.

#### Scenario: Lead time available per supplier
- GIVEN the DMS provides lead times per supplier
- WHEN the system reads lead times
- THEN the system stores lead time per supplier
- AND uses it in Planning Target and Punto de Pedido calculations

#### Scenario: Lead time not available
- GIVEN the DMS does not provide lead time data
- WHEN the system reads lead times
- THEN the system uses the configured default lead time for the branch
- AND logs a warning that lead time is using a default value

### REQ-CI-005: Cross-reference relationships
The system **shall** read cross-reference relationships from the DMS (substitutable references, alternative denominations, successor/predecessor references) and consume them as-is without redefining or duplicating them.

#### Scenario: Cross-manufacturer equivalent lookup
- GIVEN a part has equivalent references from different manufacturers in the DMS
- WHEN the system reads cross-references
- THEN the system stores the relationships as provided by the DMS
- AND uses them for stock aggregation and recommendation generation

#### Scenario: Aggregated stock across equivalents
- GIVEN two equivalent parts (SKU-A: 4 units, SKU-B: 6 units)
- WHEN the system evaluates coverage for the cross-reference group
- THEN the system aggregates stock to 10 units across both references
- AND uses the aggregated value for Punto de Pedido evaluation

### REQ-CI-006: Branch topology read
The system **shall** read branch topology from the DMS, including branch type (sucursal or centro de distribución), parent branch (for sucursales that depend on a DC), and branch managers.

#### Scenario: DC topology with dependent branches
- GIVEN a DC branch with two dependent sucursales
- WHEN the system reads branch topology
- THEN the DC is marked as centro de distribución with no parent
- AND each sucursal has parent_branch_id pointing to the DC

#### Scenario: Flat topology (no DC)
- GIVEN an organization with only sucursales and no DC
- WHEN the system reads branch topology
- THEN all branches have branch_type = sucursal and parent_branch_id = NULL

### REQ-CI-007: DMS adapter pattern
The system **shall** use an adapter interface for DMS integration, allowing different DMS implementations without modifying core logic. The adapter **shall** implement retry (3 attempts with exponential backoff) and timeout (30 seconds per call).

#### Scenario: Adapter swap
- GIVEN a new DMS type is required for a tenant
- WHEN a new adapter implementation is registered
- THEN the system uses the new adapter without changes to core logic
- AND the adapter interface contract is validated at startup

## Edge cases

- Empty catalog (branch has zero SKUs in DMS)
- Missing SKU in stock table (cold-start, no stock record exists)
- Stock quantity = 0 (eligible for replenishment)
- Lead time = 0 (instantaneous delivery — valid but unusual)
- Negative stock values (data error — system should flag and reject)
- DMS schema mismatch (column missing or renamed)
- Cross-reference cycles (A references B, B references A)
- Branch topology circular dependency (DC depends on itself)

## Acceptance criteria

- AC-1: Catalog read completes within 60 seconds for 10K SKUs
- AC-2: Stock read completes within 30 seconds for 1K SKUs per branch
- AC-3: Failed DMS read is logged with severity ERROR after 3 retries
- AC-4: Cross-reference relationships are consumed as-is, not duplicated in Part table
- AC-5: Branch topology correctly identifies DC vs sucursal and parent-child relationships
- AC-6: Adapter retry mechanism uses exponential backoff (1s, 2s, 4s) with 30s timeout

## Notes

- DMS adapter interface defined in design.md §4
- Implementation deferred to Phase 1
- System never writes to the DMS — read-only advisory layer
