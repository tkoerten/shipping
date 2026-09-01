"""Geometry unit tests: orientations, usable dims, overlap, support."""
from __future__ import annotations

from packing import Config
from packing.geometry import (
    any_orientation_fits,
    orientations,
    support_area,
    usable_dims,
)
from packing.models import Dimensions, ItemUnit, Placement

from tests.helpers import make_box, make_item


def _unit(l, w, h, weight=1.0, rotation="free"):
    return ItemUnit(
        uid=0, sku="X", description="", length_in=l, width_in=w, height_in=h,
        weight_lb=weight, rotation=rotation, stackable=True,
        max_stack_load_lb=None, fragile=False,
    )


def test_orientations_free_has_six_for_distinct_sides():
    assert len(orientations(_unit(1, 2, 3))) == 6


def test_orientations_free_dedups_cube():
    assert len(orientations(_unit(2, 2, 2))) == 1


def test_orientations_upright_keeps_height_fixed():
    oris = orientations(_unit(3, 2, 5, rotation="upright"))
    assert all(abs(dz - 5) < 1e-9 for _, _, dz in oris)
    assert len(oris) == 2


def test_orientations_fixed_is_single():
    assert orientations(_unit(3, 2, 5, rotation="fixed")) == [(3, 2, 5)]


def test_usable_dims_subtracts_two_clearances():
    box = make_box("b", 13, 9, 7)
    u = usable_dims(box, Config(clearance_in=0.25))
    assert abs(u.length_in - 12.5) < 1e-9
    assert abs(u.width_in - 8.5) < 1e-9
    assert abs(u.height_in - 6.5) < 1e-9


def test_usable_dims_exterior_subtracts_walls_and_clearance():
    box = make_box("b", 13, 9, 7, dimensions_are="exterior", wall=0.25)
    # interior = 13 - 0.5 = 12.5 etc; then minus 2*0.25 clearance = 12.0
    u = usable_dims(box, Config(clearance_in=0.25))
    assert abs(u.length_in - 12.0) < 1e-9


def test_any_orientation_fits_diagonal_only_fails():
    # A 10-long item cannot fit an 8x8x8 box in any axis-aligned orientation,
    # even though its diagonal would. We never do rotated placement.
    assert not any_orientation_fits(_unit(10, 1, 1), Dimensions(8, 8, 8))


def test_support_area_floor_is_full():
    assert support_area([], 0, 0, 0, 4, 4) == 16


def test_support_area_on_top_of_item():
    below = Placement(_unit(4, 4, 2), 0, 0, 0, 4, 4, 2)
    # Base at z=2 fully over the 4x4 top face -> full support.
    assert abs(support_area([below], 0, 0, 2, 4, 4) - 16) < 1e-9
    # Half overhanging -> half support.
    assert abs(support_area([below], 2, 0, 2, 4, 4) - 8) < 1e-9
