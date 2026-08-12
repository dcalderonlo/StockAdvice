"""Hardcoded fixture data representing one warehouse with ~30 SKUs.

Data mix:
- Fast movers (brake pads, oil filters) → high VC
- Medium movers (alternators, water pumps) → medium VC
- Slow movers (body parts, specialty sensors) → low VC
- Zero sales SKUs → cold-start scenario
- High sales SKUs → triggers
- Low stock SKUs → recommendation triggers
- Surplus stock SKUs → potential inter-branch transfer sources
"""

from __future__ import annotations

from stockadvice_spike.entities import BranchConfig, Part, SalesMovement, StockLevel


WAREHOUSE_CODE = "CD-CENTRAL"

BRANCH_CONFIG = BranchConfig(
    branch_code=WAREHOUSE_CODE,
    period_days=30,
    security_days=10,
)

# 30 automotive SKUs. lead_time_days defaults to 10 in Part.
PARTS: list[Part] = [
    Part("BP-001", "BPAD-001", "Brake Pads Front - Sedan", lead_time_days=10),
    Part("OF-001", "OFL-001", "Engine Oil Filter 5W30", lead_time_days=7),
    Part("AF-001", "AFL-001", "Air Filter Compact", lead_time_days=10),
    Part("CF-001", "CFL-001", "Cabin Filter", lead_time_days=10),
    Part("SP-001", "SPK-001", "Spark Plug Iridium", lead_time_days=14),
    Part("ALT-001", "ALT-001", "Alternator 90A", lead_time_days=21),
    Part("WP-001", "WP-001", "Water Pump Assembly", lead_time_days=14),
    Part("ST-001", "STR-001", "Starter Motor", lead_time_days=21),
    Part("TB-001", "TB-001", "Timing Belt Kit", lead_time_days=14),
    Part("CL-001", "CL-001", "Clutch Kit", lead_time_days=21),
    Part("RA-001", "RA-001", "Radiator Aluminum", lead_time_days=14),
    Part("FM-001", "FM-001", "Fuel Pump Module", lead_time_days=14),
    Part("BO-001", "BO-001", "Brake Disc Front", lead_time_days=10),
    Part("OS-001", "OS-001", "Brake Oil DOT4", lead_time_days=7),
    Part("BA-001", "BA-001", "Car Battery 60Ah", lead_time_days=10),
    Part("WI-001", "WI-001", "Wiper Blade Set", lead_time_days=7),
    Part("SH-001", "SH-001", "Shock Absorber Front", lead_time_days=14),
    Part("CV-001", "CV-001", "CV Joint Outer", lead_time_days=14),
    Part("FD-001", "FD-001", "Front Bumper Cover", lead_time_days=21),
    Part("HD-001", "HD-001", "Headlight Assembly L", lead_time_days=21),
    Part("TL-001", "TL-001", "Taillight Assembly R", lead_time_days=21),
    Part("MR-001", "MR-001", "Side Mirror Electric", lead_time_days=21),
    Part("DR-001", "DR-001", "Door Handle Outer", lead_time_days=14),
    Part("FG-001", "FG-001", "Fender Front L", lead_time_days=21),
    Part("BL-001", "BL-001", "Tailgate Lift Support", lead_time_days=14),
    Part("TS-001", "TS-001", "TPMS Sensor", lead_time_days=14),
    Part("WG-001", "WG-001", "Wheel Bearing Front", lead_time_days=14),
    Part("TR-001", "TR-001", "Tie Rod End", lead_time_days=10),
    Part("CT-001", "CT-001", "Coolant Thermostat", lead_time_days=10),
    Part("CC-001", "CC-001", "Cold-Start Sensor", lead_time_days=14),
]

# 12 months of sales history, oldest (index 0) → newest (index 11).
# Intentionally varied: trends, seasonality-ish spikes, flatlines, zeroes.
SALES_HISTORIES: dict[str, list[int]] = {
    # Fast movers
    "BP-001": [18, 19, 20, 22, 21, 23, 24, 26, 25, 28, 30, 32],  # VC2
    "OF-001": [35, 38, 36, 40, 42, 41, 45, 48, 50, 52, 55, 58],  # VC2
    "AF-001": [15, 16, 14, 17, 18, 19, 20, 22, 23, 24, 26, 28],  # VC3
    "CF-001": [12, 13, 11, 14, 15, 16, 17, 18, 19, 20, 21, 22],  # VC3
    "SP-001": [22, 23, 21, 24, 25, 26, 28, 29, 30, 32, 33, 35],  # VC2
    # Medium movers
    "ALT-001": [8, 9, 7, 8, 10, 9, 11, 10, 12, 11, 13, 14],  # VC4
    "WP-001": [6, 7, 6, 7, 8, 8, 9, 9, 10, 10, 11, 12],  # VC4
    "ST-001": [5, 6, 5, 6, 7, 7, 8, 8, 9, 9, 10, 11],  # VC5
    "TB-001": [4, 5, 4, 5, 6, 6, 7, 7, 8, 8, 9, 10],  # VC5
    "CL-001": [3, 4, 3, 4, 5, 5, 6, 6, 7, 7, 8, 9],  # VC6
    "RA-001": [2, 3, 2, 3, 4, 4, 5, 5, 6, 6, 7, 8],  # VC6
    "FM-001": [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8],  # VC6
    "BO-001": [10, 11, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20],  # VC3
    "OS-001": [20, 21, 19, 22, 23, 24, 25, 26, 27, 28, 29, 30],  # VC2
    "BA-001": [9, 10, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19],  # VC3
    # Slow movers
    "WI-001": [5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10],  # VC5
    "SH-001": [2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7],  # VC6
    "CV-001": [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6],  # VC7
    "FD-001": [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4],  # VC8
    "HD-001": [0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4],  # VC8
    "TL-001": [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4],  # VC8
    "MR-001": [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3],  # VC8
    "DR-001": [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3],  # VC8
    "FG-001": [0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3],  # VC8
    "BL-001": [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5],  # VC7
    "TS-001": [2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7],  # VC6
    "WG-001": [1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7],  # VC6
    "TR-001": [4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9],  # VC5
    "CT-001": [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8],  # VC6
    # Cold start / zero sales
    "CC-001": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}

# Current stock levels. Mix of low/surplus/normal to exercise the engine.
STOCK_LEVELS: dict[str, tuple[float, float]] = {
    # (stock_disponible, stock_en_transito)
    # Fast movers: some low stock to trigger recommendations.
    "BP-001": (15.0, 10.0),  # proposal scenario 1 reference
    "OF-001": (8.0, 0.0),
    "AF-001": (12.0, 5.0),
    "CF-001": (6.0, 0.0),
    "SP-001": (20.0, 10.0),
    # Medium movers
    "ALT-001": (4.0, 0.0),
    "WP-001": (3.0, 0.0),
    "ST-001": (5.0, 2.0),
    "TB-001": (8.0, 0.0),
    "CL-001": (2.0, 0.0),
    "RA-001": (10.0, 0.0),
    "FM-001": (4.0, 0.0),
    "BO-001": (25.0, 5.0),
    "OS-001": (30.0, 0.0),
    "BA-001": (8.0, 2.0),
    # Slow movers
    "WI-001": (12.0, 0.0),
    "SH-001": (6.0, 0.0),
    "CV-001": (4.0, 0.0),
    "FD-001": (2.0, 0.0),
    "HD-001": (1.0, 0.0),
    "TL-001": (3.0, 0.0),
    "MR-001": (2.0, 0.0),
    "DR-001": (8.0, 0.0),
    "FG-001": (5.0, 0.0),
    "BL-001": (7.0, 0.0),
    "TS-001": (10.0, 0.0),
    "WG-001": (6.0, 0.0),
    "TR-001": (15.0, 0.0),
    "CT-001": (9.0, 0.0),
    # Cold start
    "CC-001": (5.0, 0.0),
}


def get_parts() -> list[Part]:
    """Return the fixture parts list."""
    return list(PARTS)


def get_stock_levels() -> list[StockLevel]:
    """Return StockLevel objects for all fixture parts."""
    parts_by_sku = {p.internal_sku_code: p for p in PARTS}
    levels = []
    for sku, (disp, trans) in STOCK_LEVELS.items():
        part = parts_by_sku[sku]
        levels.append(StockLevel(part, WAREHOUSE_CODE, disp, trans))
    return levels


def get_sales_movements() -> list[SalesMovement]:
    """Return SalesMovement objects for all fixture parts."""
    parts_by_sku = {p.internal_sku_code: p for p in PARTS}
    movements = []
    for sku, history in SALES_HISTORIES.items():
        part = parts_by_sku[sku]
        for month_index, quantity in enumerate(history):
            movements.append(
                SalesMovement(part, WAREHOUSE_CODE, month_index, quantity)
            )
    return movements


def get_sales_history(sku: str) -> list[int]:
    """Return the 12-month sales history for a given SKU."""
    return list(SALES_HISTORIES.get(sku, []))
