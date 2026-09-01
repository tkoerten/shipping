"""Core data models for the cartonization engine.

Pure stdlib. No framework imports. Units are INCHES and POUNDS everywhere;
that is baked into field names (``*_in``, ``*_lb``) so unit mixing is visible
at the call site.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


# --------------------------------------------------------------------------- #
# Geometry primitives
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Dimensions:
    """An axis-aligned length x width x height, in inches."""

    length_in: float
    width_in: float
    height_in: float

    @property
    def volume_cu_in(self) -> float:
        return self.length_in * self.width_in * self.height_in

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.length_in, self.width_in, self.height_in)


# --------------------------------------------------------------------------- #
# Boxes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Box:
    """A shippable carton from the catalog.

    ``interior`` holds the numbers exactly as stored in the catalog. Whether
    those numbers describe the inside or the outside of the box is governed by
    ``dimensions_are`` -- the engine, not the catalog, resolves that into true
    usable interior dimensions (see :meth:`interior_dims`).
    """

    id: str
    name: str
    interior: Dimensions
    wall_thickness_in: float = 0.125
    tare_weight_lb: float = 0.0
    cost: float = 0.0
    max_gross_weight_lb: Optional[float] = None
    active: bool = True
    notes: str = ""
    dimensions_are: str = "interior"  # "interior" | "exterior"

    def interior_dims(self) -> Dimensions:
        """True interior (usable) dimensions, before clearance.

        For an "exterior" box we subtract two wall thicknesses per axis. For an
        "interior" box the stored numbers are already the inside.
        """
        if self.dimensions_are == "exterior":
            t2 = 2.0 * self.wall_thickness_in
            return Dimensions(
                max(0.0, self.interior.length_in - t2),
                max(0.0, self.interior.width_in - t2),
                max(0.0, self.interior.height_in - t2),
            )
        return self.interior

    def nominal_dims(self) -> Dimensions:
        """Dimensions used for dimensional-weight billing (catalog numbers)."""
        return self.interior

    def gross_cap_lb(self, global_cap_lb: float) -> float:
        """Effective gross-weight cap: the box's own, else the global cap."""
        if self.max_gross_weight_lb is None:
            return global_cap_lb
        return min(self.max_gross_weight_lb, global_cap_lb)


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #
ROTATION_FREE = "free"
ROTATION_UPRIGHT = "upright"
ROTATION_FIXED = "fixed"
_VALID_ROTATIONS = {ROTATION_FREE, ROTATION_UPRIGHT, ROTATION_FIXED}


@dataclass(frozen=True)
class Item:
    """An order line. ``quantity`` expands into N identical units internally."""

    sku: str
    length_in: float
    width_in: float
    height_in: float
    weight_lb: float
    description: str = ""
    quantity: int = 1
    rotation: str = ROTATION_FREE
    stackable: bool = True
    max_stack_load_lb: Optional[float] = None
    fragile: bool = False
    # "Pack as is": this item must ship in its own package, never combined with
    # any other item (SIOC-style). It still gets the smallest catalog overbox
    # that fits it.
    ship_alone: bool = False
    # Items with DIFFERENT non-null exclusion groups may never share a package
    # (e.g. keep "powder" away from "primers"). Same group or no group is fine.
    exclusion_group: Optional[str] = None
    # Free-text hazmat / commodity classification for the pack slip, e.g.
    # "ORM-D" for limited-quantity ammunition. Display-only; no packing logic.
    goods_type: str = ""

    def __post_init__(self) -> None:
        if self.rotation not in _VALID_ROTATIONS:
            raise ValueError(
                f"{self.sku}: rotation must be one of {sorted(_VALID_ROTATIONS)}, "
                f"got {self.rotation!r}"
            )
        for name, v in (
            ("length_in", self.length_in),
            ("width_in", self.width_in),
            ("height_in", self.height_in),
        ):
            if v <= 0:
                raise ValueError(f"{self.sku}: {name} must be > 0, got {v}")
        if self.weight_lb < 0:
            raise ValueError(f"{self.sku}: weight_lb must be >= 0, got {self.weight_lb}")
        if self.quantity < 1:
            raise ValueError(f"{self.sku}: quantity must be >= 1, got {self.quantity}")

    @property
    def volume_cu_in(self) -> float:
        return self.length_in * self.width_in * self.height_in


@dataclass(frozen=True)
class ItemUnit:
    """A single physical unit (quantity flattened to 1). This is what the packer

    actually places -- one ItemUnit per placement. ``uid`` is unique within a
    pack request so the balancing sweep and output can track individual units.
    """

    uid: int
    sku: str
    description: str
    length_in: float
    width_in: float
    height_in: float
    weight_lb: float
    rotation: str
    stackable: bool
    max_stack_load_lb: Optional[float]
    fragile: bool
    ship_alone: bool = False
    exclusion_group: Optional[str] = None
    goods_type: str = ""

    @property
    def volume_cu_in(self) -> float:
        return self.length_in * self.width_in * self.height_in

    @property
    def longest_in(self) -> float:
        return max(self.length_in, self.width_in, self.height_in)

    @property
    def footprint_in2(self) -> float:
        # Largest of the three face areas (used only for ordering heuristics).
        l, w, h = self.length_in, self.width_in, self.height_in
        return max(l * w, l * h, w * h)


def expand_items(items: list[Item]) -> list[ItemUnit]:
    """Flatten quantities into individual placeable units with stable uids."""
    units: list[ItemUnit] = []
    uid = 0
    for it in items:
        for _ in range(it.quantity):
            units.append(
                ItemUnit(
                    uid=uid,
                    sku=it.sku,
                    description=it.description,
                    length_in=it.length_in,
                    width_in=it.width_in,
                    height_in=it.height_in,
                    weight_lb=it.weight_lb,
                    rotation=it.rotation,
                    stackable=it.stackable,
                    max_stack_load_lb=it.max_stack_load_lb,
                    fragile=it.fragile,
                    ship_alone=it.ship_alone,
                    exclusion_group=it.exclusion_group,
                    goods_type=it.goods_type,
                )
            )
            uid += 1
    return units


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Config:
    """Per-request packing configuration (with catalog-saved defaults)."""

    dunnage_reserve_pct: float = 0.15
    clearance_in: float = 0.25
    max_package_weight_lb: float = 65.0
    dim_divisor: float = 139.0
    allow_split: bool = True
    max_packages: int = 5
    # Wall-clock budget per box for randomized restarts (see packer).
    time_budget_ms: int = 250
    # RNG seed; fixed so identical input yields identical output.
    seed: int = 1337

    def __post_init__(self) -> None:
        if not (0.0 <= self.dunnage_reserve_pct < 1.0):
            raise ValueError("dunnage_reserve_pct must be in [0, 1)")
        if self.clearance_in < 0:
            raise ValueError("clearance_in must be >= 0")
        if self.dim_divisor <= 0:
            raise ValueError("dim_divisor must be > 0")
        if self.max_packages < 1:
            raise ValueError("max_packages must be >= 1")


# --------------------------------------------------------------------------- #
# Placements & results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Placement:
    """A placed unit: its origin corner and its axis-aligned extent (inches).

    ``position`` is the minimum (x, y, z) corner inside the usable box space.
    ``orientation`` is the chosen extent (dx, dy, dz) after rotation.
    """

    unit: ItemUnit
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float

    @property
    def x2(self) -> float:
        return self.x + self.dx

    @property
    def y2(self) -> float:
        return self.y + self.dy

    @property
    def z2(self) -> float:
        return self.z + self.dz

    @property
    def volume_cu_in(self) -> float:
        return self.dx * self.dy * self.dz


@dataclass
class PackedBox:
    """A successful single-box packing (one physical package)."""

    box: Box
    placements: list[Placement]
    config: Config

    # ---- weights ----
    @property
    def item_weight_lb(self) -> float:
        return sum(p.unit.weight_lb for p in self.placements)

    @property
    def gross_weight_lb(self) -> float:
        return self.item_weight_lb + self.box.tare_weight_lb

    @property
    def dim_weight_lb(self) -> float:
        import math

        d = self.box.nominal_dims()
        return math.ceil(d.volume_cu_in / self.config.dim_divisor)

    @property
    def billable_weight_lb(self) -> float:
        return max(self.gross_weight_lb, self.dim_weight_lb)

    # ---- volume / fill ----
    @property
    def usable_volume_cu_in(self) -> float:
        from .geometry import usable_dims

        return usable_dims(self.box, self.config).volume_cu_in

    @property
    def item_volume_cu_in(self) -> float:
        return sum(p.volume_cu_in for p in self.placements)

    @property
    def fill_pct(self) -> float:
        uv = self.usable_volume_cu_in
        return 100.0 * self.item_volume_cu_in / uv if uv > 0 else 0.0

    @property
    def void_volume_cu_in(self) -> float:
        return max(0.0, self.usable_volume_cu_in - self.item_volume_cu_in)


@dataclass
class PackResult:
    """Top-level result of a pack request."""

    packages: list[PackedBox]
    explanation: list[str]
    ok: bool
    message: str = ""

    @property
    def total_packages(self) -> int:
        return len(self.packages)

    @property
    def total_billable_weight_lb(self) -> float:
        return sum(p.billable_weight_lb for p in self.packages)

    @property
    def total_box_cost(self) -> float:
        return sum(p.box.cost for p in self.packages)
