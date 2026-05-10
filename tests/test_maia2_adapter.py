"""Small tests for Maia-2 adapter helpers."""

from src.engines.maia2_adapter import qualifying_policy_items, resolve_device, sorted_policy_items


def test_sorted_policy_items_orders_descending() -> None:
    items = sorted_policy_items({"a2a4": 0.05, "e2e4": 0.3, "d2d4": 0.2})
    assert items == [("e2e4", 0.3), ("d2d4", 0.2), ("a2a4", 0.05)]


def test_qualifying_policy_items_respects_threshold() -> None:
    items = qualifying_policy_items(
        {"a2a4": 0.05, "e2e4": 0.3, "d2d4": 0.2},
        min_probability=0.10,
    )
    assert items == [("e2e4", 0.3), ("d2d4", 0.2)]


def test_resolve_device_auto_returns_supported_backend() -> None:
    assert resolve_device("auto") in {"cpu", "mps"}
