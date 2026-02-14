"""
Unified database module providing access to all database operations.
This module consolidates imports from db submodules organized by entity type.
"""

# Firestore connection
from db.firestore import get_db_connection, init_database

# User operations
from db.users import get_pass, get_party, get_user_type, get_user_productivity

# Order operations
from db.orders import (
    add_orders_to_db,
    get_orders_from_db,
    get_order_details,
    update_status,
    get_orders_grouped_by_sku,
    get_product_image_url,
    update_orders_for_sku,
    calculate_order_counts,
    out_of_stock,
)

# Return operations
from db.returns import (
    get_returns_from_db,
    enter_return_data,
    get_returns_grouped_by_sku,
    accept_returns_by_sku,
)

# Cancelled order operations
from db.cancelled import (
    get_cancelled_from_db,
    accept_cancelled,
)

# AWB operations
from db.awb import (
    pending_awb,
    pending_awbs_list,
    remove_pending_awb,
)

from db.out_of_stock import (
    get_out_of_stock_from_db,
    accept_out_of_stock,
)

__all__ = [
    # Firestore
    "get_db_connection",
    "init_database",
    # Users
    "get_pass",
    "get_party",
    "get_user_type",
    "get_user_productivity",
    # Orders
    "add_orders_to_db",
    "get_orders_from_db",
    "get_order_details",
    "update_status",
    "get_orders_grouped_by_sku",
    "get_product_image_url",
    "update_orders_for_sku",
    "calculate_order_counts",
    "out_of_stock",
    # Returns
    "get_returns_from_db",
    "enter_return_data",
    "get_returns_grouped_by_sku",
    "accept_returns_by_sku",
    # Cancelled
    "get_cancelled_from_db",
    "accept_cancelled",
    # AWB
    "pending_awb",
    "pending_awbs_list",
    "remove_pending_awb",
    # Out of Stock
    "get_out_of_stock_from_db",
    "accept_out_of_stock",
]
