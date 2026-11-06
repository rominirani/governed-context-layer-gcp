"""Runnable MCP Server for Google Antigravity Manager (`roast_context_mcp_server.py`).

Lets you register the Roast & Co. Governed Context Layer directly inside Google
Antigravity Manager (`~/.gemini/antigravity/mcp_config.json`) and run natural-language
queries against both the Knowledge Catalog Context Set and the 4 governed database tools!
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Support both mcp 2.x (MCPServer) and mcp 1.x (FastMCP)
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]

from context_layer_gateway import ContextLayerGateway, RestockRequestPayload
from knowledge_catalog_setup import KnowledgeCatalogConfig, simulate_lookup_context_yaml

mcp = FastMCP("roast-and-co-context-layer")
_GATEWAY = ContextLayerGateway()


@mcp.tool()
def lookup_roast_context_catalog(project_id: str = "roast-and-co-prod") -> str:
    """Look up the Google Cloud Knowledge Catalog Context Set YAML for Roast & Co.

    Always call this tool first when a user asks how 'Net Store Revenue' or
    'At-Risk Inventory' is defined, or asks about PII governance rules on `customers`.
    """
    cfg = KnowledgeCatalogConfig(project_id=project_id)
    return simulate_lookup_context_yaml(cfg)


@mcp.tool()
def get_store_net_revenue_summary(city_filter: str = "ALL") -> list[dict[str, Any]]:
    """Return verified Net Store Revenue (COMPLETED orders minus discounts) per store.

    Args:
        city_filter: City name ('Cape Town', 'Johannesburg', 'Durban') or 'ALL'.
    """
    records = _GATEWAY.get_store_net_revenue_summary(
        city_filter=city_filter, caller_identity="antigravity-manager-mcp"
    )
    return [item.model_dump(mode="json") for item in records]


@mcp.tool()
def get_low_stock_inventory_alerts(store_id_filter: str = "ALL") -> list[dict[str, Any]]:
    """List store bean & milk inventory items at or below their reorder_threshold.

    Excludes confidential wholesale `supplier_cost_usd`.
    """
    alerts = _GATEWAY.get_low_stock_inventory_alerts(
        store_id_filter=store_id_filter, caller_identity="antigravity-manager-mcp"
    )
    return [item.model_dump(mode="json") for item in alerts]


@mcp.tool()
def lookup_vip_orders_masked(loyalty_tier_filter: str = "GOLD") -> list[dict[str, Any]]:
    """Return recent COMPLETED orders for GOLD or SILVER loyalty members with PII masked.

    Customer email, phone_number, and home_address are never exposed.
    """
    orders = _GATEWAY.lookup_vip_orders_masked(
        loyalty_tier_filter=loyalty_tier_filter, caller_identity="antigravity-manager-mcp"
    )
    return [item.model_dump(mode="json") for item in orders]


@mcp.tool()
def create_bean_restock_request(
    store_id: str,
    sku_id: str,
    requested_quantity: float,
    requested_by_email: str = "lindiwe@roastandco.co.za",
) -> dict[str, Any]:
    """Submit a governed bean or milk restock request (bounded between 1 and 200 units).

    Requires OIDC caller identity (`requested_by_email`) to match `stores.manager_email`
    or `hq-ops@roastandco.co.za`.
    """
    payload = RestockRequestPayload(
        store_id=store_id,
        sku_id=sku_id,
        requested_quantity=Decimal(str(requested_quantity)),
        requested_by_email=requested_by_email,
    )
    return _GATEWAY.create_bean_restock_request(
        payload, caller_identity="antigravity-manager-mcp"
    )


@mcp.tool()
def trace_delayed_supplier_vip_impact(
    shipment_status_filter: str = "DELAYED_PORT_CONGESTION",
) -> list[dict[str, Any]]:
    """Trace multi-hop supply-chain blast radius: Delayed Supplier -> Low-Stock SKU -> Store -> GOLD VIP Customers."""
    records = _GATEWAY.trace_delayed_supplier_vip_impact(
        shipment_status_filter=shipment_status_filter,
        caller_identity="antigravity-manager-mcp",
    )
    return [item.model_dump(mode="json") for item in records]


@mcp.tool()
def screen_prompt_with_model_armor(user_prompt: str) -> dict[str, Any]:
    """Screen an incoming user prompt through Google Cloud Model Armor + Sensitive Data Protection."""
    return _GATEWAY.model_armor.sanitize_user_prompt(user_prompt).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
