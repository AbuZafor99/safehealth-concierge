"""Tests for the drug interaction blacklist — read-only, no vault fixture needed."""
import pytest
from mcp_server.server import check_interaction


# ── Known dangerous pairs ──────────────────────────────────────────────────

@pytest.mark.parametrize("med_a, med_b", [
    ("Lisinopril",   "Ibuprofen"),
    ("Warfarin",     "Aspirin"),
    ("Warfarin",     "Ibuprofen"),
    ("Warfarin",     "Atorvastatin"),
    ("Atorvastatin", "Grapefruit"),
    ("Metformin",    "Alcohol"),
    ("Aspirin",      "Ibuprofen"),
])
def test_known_interaction_is_detected(med_a, med_b):
    result = check_interaction(med_a, med_b)
    assert result["has_interaction"] is True, f"Expected interaction: {med_a} + {med_b}"
    assert "WARNING" in result["warning"]


# ── Symmetry — order of arguments must not matter ─────────────────────────

@pytest.mark.parametrize("med_a, med_b", [
    ("Ibuprofen",    "Lisinopril"),   # reversed
    ("Aspirin",      "Warfarin"),
    ("Ibuprofen",    "Warfarin"),
])
def test_interaction_check_is_symmetric(med_a, med_b):
    result = check_interaction(med_a, med_b)
    assert result["has_interaction"] is True, f"Symmetric check failed: {med_a} + {med_b}"


# ── Safe combinations ──────────────────────────────────────────────────────

@pytest.mark.parametrize("med_a, med_b", [
    ("Vitamin D",    "Omega-3"),
    ("Lisinopril",   "Metformin"),
    ("Metformin",    "Atorvastatin"),
    ("Vitamin D",    "Lisinopril"),
])
def test_no_interaction_for_safe_pairs(med_a, med_b):
    result = check_interaction(med_a, med_b)
    assert result["has_interaction"] is False, f"Unexpected interaction: {med_a} + {med_b}"
    assert "No documented" in result["warning"]


# ── Response structure ─────────────────────────────────────────────────────

def test_response_always_contains_required_fields():
    result = check_interaction("Warfarin", "Aspirin")
    assert "medication_a"   in result
    assert "medication_b"   in result
    assert "has_interaction" in result
    assert "warning"        in result


def test_unknown_medication_pair_returns_no_interaction():
    result = check_interaction("FakeDrug", "AnotherFakeDrug")
    assert result["has_interaction"] is False
