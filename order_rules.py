"""Shared order status transition policy used by customer and admin workflows."""

ALLOWED_STATUS_MOVES = {
    "Placed": {"Packed", "Cancelled"},
    # Compatibility for legacy orders created before Step 57 normalization.
    "Pending": {"Packed", "Cancelled"},
    "Packed": {"Shipped"},
    "Shipped": {"Delivered"},
    "Delivered": set(),
    "Cancelled": set(),
}
