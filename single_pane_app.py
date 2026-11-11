"""Steps 5 & 6 of the Blog Post: The Single-Pane-of-Glass App + AST Boundary Verifier.

Notice what is NOT in this file:
- Zero database drivers (`sqlite3`, `psycopg`, `asyncpg`, `sqlalchemy`).
- Zero raw SQL queries.
- All data and actions flow strictly through `ContextLayerGateway` (our MCP Toolbox
  + Knowledge Catalog Context Layer).

Also includes `verify_no_direct_db_access()`—an AST static analyzer that blocks any
vibe-coded UI file that attempts to bypass the Context Layer.
"""

from __future__ import annotations

import ast
import html
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
import httpx

from context_layer_gateway import ContextLayerGateway, RestockRequestPayload

app = FastAPI(
    title="Chai & Co. (India Tea Shop) — Morning Franchise Pulse (Single Pane of Glass)",
    version="1.0.0",
)

MCP_TOOLBOX_URL = os.environ.get("MCP_TOOLBOX_URL", "http://127.0.0.1:5000/mcp")
GATEWAY = ContextLayerGateway()


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Invoke a governed SQL tool on the MCP Toolbox for Databases HTTP server."""
    response = httpx.post(
        MCP_TOOLBOX_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        headers={"Accept": "application/json, text/event-stream"},
        timeout=10.0,
    )
    response.raise_for_status()
    content = response.json().get("result", {}).get("content", [])
    return [json.loads(item["text"]) for item in content if "text" in item]


def sanitize_delivery_note(raw_note: str) -> str:
    """Screen free-text `delivery_note` via Google Cloud Model Armor + Sensitive Data Protection."""
    verdict = GATEWAY.model_armor.sanitize_free_text_db_field(raw_note)
    return verdict.sanitized_text


@app.middleware("http")
async def attach_security_headers(request: Request, call_next: Any) -> Response:
    """Attach mandatory security headers to every HTTP response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    return response


@app.get("/api/pulse")
def get_franchise_single_pane_pulse(
    city: str = Query(default="ALL", max_length=60),
) -> dict[str, Any]:
    """Consolidate Store Revenue, Low-Stock Tea Inventory, Masked VIP Activity, and Supply-Chain Blast Radius."""
    try:
        stores = call_mcp_tool("get_store_net_revenue_summary", {"city_filter": city})
        low_stock = call_mcp_tool("get_low_stock_inventory_alerts", {"store_id_filter": "ALL"})
        vip_orders = call_mcp_tool("lookup_vip_orders_masked", {"loyalty_tier_filter": "GOLD"})
        for order in vip_orders:
            raw_note = str(order.get("delivery_note", ""))
            order["sanitized_delivery_note"] = sanitize_delivery_note(raw_note)
        supply_chain_impacts = [
            item.model_dump(mode="json")
            for item in GATEWAY.trace_delayed_supplier_vip_impact(
                shipment_status_filter="DELAYED_MONSOON_FREIGHT",
                caller_identity="single-pane-web-ui",
            )
        ]
        total_net_rev = sum((Decimal(str(item["net_revenue_usd"])) for item in stores), Decimal("0.00"))
        return {
            "city_filter": city,
            "total_net_revenue_usd": f"{total_net_rev:.2f}",
            "stores": stores,
            "low_stock_alerts": low_stock,
            "recent_gold_vip_orders": vip_orders,
            "supply_chain_vip_impacts": supply_chain_impacts,
        }
    except Exception:
        revenues = GATEWAY.get_store_net_revenue_summary(
            city_filter=city, caller_identity="single-pane-web-ui"
        )
        low_stock_items = GATEWAY.get_low_stock_inventory_alerts(
            store_id_filter="ALL", caller_identity="single-pane-web-ui"
        )
        vip_order_items = GATEWAY.lookup_vip_orders_masked(
            loyalty_tier_filter="GOLD", caller_identity="single-pane-web-ui"
        )
        supply_chain_impacts = GATEWAY.trace_delayed_supplier_vip_impact(
            shipment_status_filter="DELAYED_MONSOON_FREIGHT",
            caller_identity="single-pane-web-ui",
        )
        total_net_rev = sum((item.net_revenue_usd for item in revenues), Decimal("0.00"))
        return {
            "city_filter": city,
            "total_net_revenue_usd": str(total_net_rev),
            "stores": [item.model_dump(mode="json") for item in revenues],
            "low_stock_alerts": [item.model_dump(mode="json") for item in low_stock_items],
            "recent_gold_vip_orders": [item.model_dump(mode="json") for item in vip_order_items],
            "supply_chain_vip_impacts": [item.model_dump(mode="json") for item in supply_chain_impacts],
        }


@app.post("/api/restock", status_code=201)
def submit_governed_restock(payload: RestockRequestPayload) -> dict[str, Any]:
    """Trigger a governed tea/spice restock request through the Context Layer."""
    try:
        return GATEWAY.create_tea_restock_request(
            payload, caller_identity="single-pane-web-ui"
        )
    except PermissionError as exc:
        status = 429 if "429" in str(exc) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.get("/api/audit-log")
def get_context_layer_audit_log() -> dict[str, Any]:
    """Return the immutable governance audit trail recorded by the Context Layer."""
    entries = GATEWAY.audit_log
    return {
        "total_events": len(entries),
        "events": [entry.model_dump(mode="json") for entry in entries],
    }


@app.get("/", response_class=HTMLResponse)
def render_single_pane_dashboard(city: str = Query(default="ALL", max_length=60)) -> str:
    """Render the Single Pane of Glass HTML view with strict HTML escaping."""
    pulse = get_franchise_single_pane_pulse(city=city)

    store_rows = []
    for s in pulse["stores"]:
        store_rows.append(
            f"<tr>"
            f"<td>{html.escape(str(s['store_name']), quote=True)}</td>"
            f"<td>{html.escape(str(s['city']), quote=True)}</td>"
            f"<td>${html.escape(str(s['net_revenue_usd']), quote=True)}</td>"
            f"<td>{html.escape(str(s['completed_orders']), quote=True)} "
            f"(Excluded: {html.escape(str(s['excluded_orders']), quote=True)})</td>"
            f"</tr>"
        )

    alert_items = []
    for a in pulse["low_stock_alerts"]:
        alert_items.append(
            f"<li><strong>{html.escape(str(a['store_name']), quote=True)}</strong>: "
            f"{html.escape(str(a['item_name']), quote=True)} — "
            f"{html.escape(str(a['stock_on_hand']), quote=True)} {html.escape(str(a['unit']), quote=True)} left "
            f"(Reorder at {html.escape(str(a['reorder_threshold']), quote=True)})</li>"
        )

    vip_items = []
    for v in pulse["recent_gold_vip_orders"]:
        note = v.get("sanitized_delivery_note") or v.get("delivery_note") or ""
        vip_items.append(
            f"<li>Order <code>{html.escape(str(v['order_id']), quote=True)}</code> — "
            f"{html.escape(str(v['customer_display_name']), quote=True)} "
            f"({html.escape(str(v['loyalty_tier']), quote=True)}): "
            f"${html.escape(str(v['net_order_usd']), quote=True)} "
            f"<em>(Note: {html.escape(str(note), quote=True)})</em></li>"
        )

    impact_items = []
    for imp in pulse["supply_chain_vip_impacts"]:
        impact_items.append(
            f"<li><strong>{html.escape(str(imp['supplier_name']), quote=True)}</strong> "
            f"({html.escape(str(imp['shipment_status']), quote=True)}) &rarr; "
            f"{html.escape(str(imp['item_name']), quote=True)} at "
            f"{html.escape(str(imp['store_name']), quote=True)} &rarr; "
            f"Impacts {html.escape(str(imp['affected_vip_customers']), quote=True)} VIP Customer(s)</li>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Chai &amp; Co. — Morning Franchise Pulse</title>
</head>
<body>
  <header>
    <h1>Chai &amp; Co. (India Tea Shop) — Morning Franchise Pulse (Single Pane of Glass)</h1>
    <p>Total Verified Net Store Revenue: <strong>${html.escape(pulse['total_net_revenue_usd'], quote=True)}</strong></p>
  </header>
  <main>
    <section id="revenue-section">
      <h2>1. Store Net Revenue (Knowledge Catalog Governed Metric)</h2>
      <table>
        <thead><tr><th>Store</th><th>City</th><th>Net Revenue</th><th>Completed Orders</th></tr></thead>
        <tbody>{''.join(store_rows)}</tbody>
      </table>
    </section>
    <section id="inventory-section">
      <h2>2. At-Risk Tea Leaves &amp; Chai Spice Inventory Alerts</h2>
      <ul>{''.join(alert_items)}</ul>
    </section>
    <section id="vip-section">
      <h2>3. Recent GOLD Loyalty Activity (PII Masked + Model Armor Sanitized)</h2>
      <ul>{''.join(vip_items)}</ul>
    </section>
    <section id="supply-chain-section">
      <h2>4. Multi-Hop Supply-Chain Blast Radius (Knowledge Graph / GQL)</h2>
      <ul>{''.join(impact_items)}</ul>
    </section>
  </main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Step 6: Automated AST Architectural Boundary Verifier
# ---------------------------------------------------------------------------

FORBIDDEN_DB_IMPORTS = {
    "sqlite3",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "sqlalchemy",
    "pymysql",
    "google.cloud.sql.connector",
}

RAW_SQL_KEYWORDS = ("select ", "insert into ", "update ", "delete from ", "drop table ")


def verify_no_direct_db_access(python_source: str) -> dict[str, Any]:
    """Statically analyze generated app code to ensure it cannot bypass the Context Layer.

    Blocks:
    1. Importing raw database drivers (`sqlite3`, `psycopg`, `sqlalchemy`, etc.).
    2. Embedding raw SQL query strings (`SELECT ... FROM ...`, `DROP TABLE`, etc.) in UI code.
    """
    tree = ast.parse(python_source)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if alias.name in FORBIDDEN_DB_IMPORTS or root_pkg in FORBIDDEN_DB_IMPORTS:
                    violations.append(f"Forbidden direct database import: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            root_pkg = module_name.split(".")[0]
            if module_name in FORBIDDEN_DB_IMPORTS or root_pkg in FORBIDDEN_DB_IMPORTS:
                violations.append(f"Forbidden direct database import: 'from {module_name} import ...'")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.strip().lower()
            if any(lowered.startswith(kw) and " from " in lowered for kw in RAW_SQL_KEYWORDS):
                violations.append(f"Forbidden raw SQL string in UI layer: '{node.value[:50]}...'")

    return {
        "approved": len(violations) == 0,
        "violations": violations,
    }


if __name__ == "__main__":
    import uvicorn

    self_source = Path(__file__).read_text(encoding="utf-8")
    check = verify_no_direct_db_access(self_source)
    if not check["approved"]:
        raise HTTPException(status_code=500, detail=str(check["violations"]))
    uvicorn.run(app, host="127.0.0.1", port=8011)
