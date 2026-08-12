# sector-configuration — Specification

## Purpose

Enables sector-specific terminology, classification codes, lifecycle stages, and special categories without modifying core logic. The system ships with a default configuration (automotive aftermarket) and supports adding other sectors (pharmaceutical, hardware, manufacturing, etc.) by configuring terminology, classification, and lifecycle rules.

## Requirements

### REQ-SC-001: Sector configuration model
The system **shall** store sector configuration as a `sector_key` + `config_json` containing: terminology labels, classification thresholds, lifecycle rules, and special categories.

#### Scenario: Default automotive configuration
- GIVEN a new tenant is created without specifying a sector
- WHEN the system initializes the tenant
- THEN the default sector is "automotive_aftermarket"
- AND the configuration includes automotive terminology (e.g., "Part", "Branch", "Warehouse Manager")

#### Scenario: Custom sector added
- GIVEN an admin adds a "pharmaceutical" sector configuration
- WHEN the sector is saved
- THEN the config_json includes pharmaceutical-specific terminology, classification codes, and lifecycle rules
- AND the core logic (formulas, recommendation engine) is unchanged

### REQ-SC-002: Sector-specific terminology
The system **shall** use sector-specific terminology in the UI, notifications, and exports. Terminology includes entity names, role titles, and domain-specific labels.

#### Scenario: Automotive terminology
- GIVEN the sector is "automotive_aftermarket"
- WHEN the dashboard renders
- THEN labels use automotive terms (e.g., "Part", "SKU", "Warehouse Manager")

#### Scenario: Pharmaceutical terminology
- GIVEN the sector is "pharmaceutical"
- WHEN the dashboard renders
- THEN labels use pharmaceutical terms (e.g., "Product", "Item Code", "Pharmacy Manager")

### REQ-SC-003: Sector-specific classification codes
The system **shall** support sector-specific Volume Class thresholds and Lifecycle Stage codes. The core classification engine uses the sector's configuration to determine thresholds.

#### Scenario: Automotive Volume Class thresholds
- GIVEN the sector is "automotive_aftermarket"
- WHEN the classification engine runs
- THEN it uses the automotive thresholds (VC1 > 250, VC2 121–250, etc.)

#### Scenario: Custom Volume Class thresholds
- GIVEN the sector is "hardware" with custom thresholds (VC1 > 500, VC2 201–500, etc.)
- WHEN the classification engine runs
- THEN it uses the hardware-specific thresholds
- AND the core engine logic is unchanged

### REQ-SC-004: Sector-specific lifecycle stages
The system **shall** support sector-specific lifecycle stage codes and their behavioral rules. The default lifecycle stages (New, Active, Pre-Obsolete, Obsolete, Inactive, Non-Stocking) can be renamed or extended per sector.

#### Scenario: Automotive lifecycle stages
- GIVEN the sector is "automotive_aftermarket"
- WHEN the classification engine evaluates lifecycle
- THEN it uses the default stages (N1/N2/N3, OBS-S/OBS-N/OBS-P/OBS-R, Inactive, NS-C/NS-NS)

#### Scenario: Extended lifecycle stages
- GIVEN a sector adds a custom lifecycle stage "Quarantine"
- WHEN the classification engine runs
- THEN SKUs can be classified as "Quarantine"
- AND the sector configuration defines the behavior for Quarantine SKUs (e.g., excluded from recommendations)

### REQ-SC-005: Universal formulas
The system **shall** apply the same core formulas (Planning Target, Punto de Pedido, Cantidad de Pedido) across all sectors. Sector configuration affects labels and rules, not the math.

#### Scenario: Same formulas, different labels
- GIVEN two tenants: one automotive, one pharmaceutical
- WHEN both run replenishment calculations
- THEN the formulas produce identical results for the same input data
- AND only the UI labels and terminology differ

### REQ-SC-006: Sector configuration management
The system **shall** allow administrators to view, create, and modify sector configurations through the admin panel.

#### Scenario: Admin creates sector configuration
- GIVEN an admin wants to add a "manufacturing" sector
- WHEN the admin creates a new sector configuration
- THEN the admin specifies: sector_key, terminology, classification thresholds, lifecycle rules
- AND the configuration is saved and available for tenant assignment

#### Scenario: Admin modifies sector configuration
- GIVEN an existing sector configuration needs updated thresholds
- WHEN the admin modifies the configuration
- THEN the changes apply to all tenants using that sector
- AND the next classification pass uses the new thresholds

## Edge cases

- Sector configuration with missing required fields (system should validate and reject)
- Tenant assigned to a non-existent sector (system should default to automotive_aftermarket)
- Sector configuration modified while classification pass is running (system should use the config at run start)
- Custom lifecycle stage with no behavioral rules defined (system should treat as "view only")
- Sector configuration deleted while tenants are using it (system should prevent deletion or reassign tenants)
- Terminology label contains HTML or script tags (system should sanitize)

## Acceptance criteria

- AC-1: Default sector is "automotive_aftermarket" for new tenants
- AC-2: Sector-specific terminology is used in UI, notifications, and exports
- AC-3: Classification engine uses sector-specific thresholds
- AC-4: Core formulas are identical across all sectors (only labels/rules differ)
- AC-5: Admin can create, view, and modify sector configurations
- AC-6: Sector configuration changes apply to all tenants using that sector
- AC-7: Custom lifecycle stages can be added with sector-specific behavioral rules

## Notes

- Formulas are universal inventory management concepts; sector-specific aspects are labels and rules
- Sector configuration stored in `SectorConfiguration` model with `sector_key` + `config_json`
- Automotive aftermarket is the default and primary v1 sector
