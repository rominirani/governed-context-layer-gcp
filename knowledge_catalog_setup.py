"""Step 2 of the Blog Post: Registering Semantic Context in Google Cloud Knowledge Catalog
and Authoring a Multi-Hop Supply Chain Property Graph (`CREATE PROPERTY GRAPH`).

Demonstrates how to build and inspect:
1. A Knowledge Catalog Context Set (`create_entry_group` with `type="context-set"`).
2. Rich Table & Business Glossary Entries (`upsert_entry`) with `dataplex-types.global.document`,
   `dataplex-types.global.overview`, `dataplex-types.global.descriptions`, and
   `dataplex-types.global.queries` aspects.
3. Explicit `schema-join` and `definition` Entry Links (`upsert_entry_link`) so coding agents
   never hallucinate table joins or miscalculate 'Net Store Revenue'.
4. Simulated `lookup_context` YAML output (matching `gcloud dataplex context lookup`).
5. BigQuery Property Graph DDL (`CREATE OR REPLACE PROPERTY GRAPH`) and ISO GQL query for
   Gap 4 (Multi-Hop Supply Chain Knowledge Graph traversal).
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeCatalogConfig(BaseModel):
    """Configuration for Chai & Co.'s Knowledge Catalog Context Set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(default="chai-and-co-prod", min_length=3)
    location: str = Field(default="asia-south1")
    entry_group_id: str = Field(default="chai-and-co-context-set")


def build_context_set_payload(cfg: KnowledgeCatalogConfig) -> dict[str, Any]:
    """Build the payload for `create_entry_group` (`type="context-set"`).

    Maps directly to the `datacloud_knowledge_catalog_remote` `create_entry_group` tool.
    """
    return {
        "projectId": cfg.project_id,
        "location": cfg.location,
        "entryGroupId": cfg.entry_group_id,
        "type": "context-set",
        "displayName": "Chai & Co. (India Tea Shop) Franchise Context Set",
        "description": (
            "Governed semantic layer for Chai & Co. tea outlets across Mumbai, Bengaluru, "
            "and Delhi, covering orders, loyalty customers, tea estate suppliers, and "
            "chai spice inventory. Enforces Net Store Revenue rules and PII masking."
        ),
        "labels": {
            "domain": "franchise-operations",
            "governance": "pii-masked",
        },
    }


def build_glossary_and_table_entries(cfg: KnowledgeCatalogConfig) -> list[dict[str, Any]]:
    """Build `upsert_entry` payloads for Business Glossary terms and Cloud SQL table context."""
    base_group = (
        f"projects/{cfg.project_id}/locations/{cfg.location}/entryGroups/{cfg.entry_group_id}"
    )
    doc_entry_type = "projects/dataplex-types/locations/global/entryTypes/document"

    return [
        {
            "name": f"{base_group}/entries/glossary-net-store-revenue",
            "entryType": doc_entry_type,
            "displayName": "Net Store Revenue (Official Metric Definition)",
            "description": (
                "Official franchise revenue calculation: SUM(gross_amount_usd - discount_usd) "
                "strictly filtered to orders WHERE status = 'COMPLETED'."
            ),
            "allowMissing": True,
            "aspects": {
                "dataplex-types.global.document": {
                    "title": "Net Store Revenue",
                    "type": "glossary",
                    "summary": (
                        "Net Store Revenue equals gross_amount_usd minus discount_usd for "
                        "COMPLETED orders only. Never include REFUNDED or CANCELLED orders."
                    ),
                },
                "dataplex-types.global.overview": {
                    "contentType": "MARKDOWN",
                    "content": (
                        "# Net Store Revenue\n\n"
                        "- **Formula**: `SUM(gross_amount_usd - discount_usd) FILTER (WHERE status = 'COMPLETED')`\n"
                        "- **Excluded Statuses**: `'REFUNDED'`, `'CANCELLED'`\n"
                        "- **Why It Matters**: Counting refunded or cancelled orders overstates store revenue by 25%+."
                    ),
                },
            },
        },
        {
            "name": f"{base_group}/entries/table-orders-context",
            "entryType": doc_entry_type,
            "displayName": "Cloud SQL Table: chai_and_co.public.orders",
            "description": "Customer chai and snack orders across all Chai & Co. franchise locations.",
            "system": "CLOUD_SQL",
            "platform": "GCP",
            "allowMissing": True,
            "aspects": {
                "dataplex-types.global.document": {
                    "title": "orders (Cloud SQL PostgreSQL)",
                    "type": "table-context",
                    "summary": "Transactional order records linked to stores and loyalty customers.",
                },
                "dataplex-types.global.descriptions": {
                    "fields": [
                        {"name": "order_id", "description": "Primary key order identifier (e.g. ord-9001)."},
                        {"name": "store_id", "description": "Foreign key to stores.store_id."},
                        {"name": "customer_id", "description": "Foreign key to customers.customer_id."},
                        {
                            "name": "status",
                            "description": "Order lifecycle state: COMPLETED, REFUNDED, or CANCELLED. Always filter for COMPLETED when computing revenue!",
                        },
                        {
                            "name": "gross_amount_usd",
                            "description": "Pre-discount order amount in USD. Do not sum without subtracting discount_usd and filtering status = 'COMPLETED'.",
                        },
                        {"name": "discount_usd", "description": "Loyalty or promotional discount in USD."},
                        {
                            "name": "delivery_note",
                            "description": "UNSTRUCTURED FREE TEXT: Must be sanitized through Google Cloud Model Armor (Sensitive Data Protection + Indirect Prompt Injection filter) before returning to agents.",
                        },
                    ]
                },
                "dataplex-types.global.queries": {
                    "queries": [
                        {
                            "title": "Verified Net Store Revenue by Store",
                            "description": "Approved semantic query for daily tea shop revenue.",
                            "query": (
                                "SELECT s.store_id, s.store_name, "
                                "COALESCE(SUM(o.gross_amount_usd - o.discount_usd) FILTER (WHERE o.status = 'COMPLETED'), 0.00) AS net_revenue_usd "
                                "FROM stores s LEFT JOIN orders o ON o.store_id = s.store_id GROUP BY s.store_id, s.store_name;"
                            ),
                        }
                    ]
                },
            },
        },
        {
            "name": f"{base_group}/entries/table-customers-context",
            "entryType": doc_entry_type,
            "displayName": "Cloud SQL Table: chai_and_co.public.customers (PII RESTRICTED)",
            "description": "Loyalty program members. Contains restricted PII columns (email, phone_number, home_address).",
            "system": "CLOUD_SQL",
            "platform": "GCP",
            "labels": {"pii_classification": "confidential"},
            "allowMissing": True,
            "aspects": {
                "dataplex-types.global.document": {
                    "title": "customers (PII Restricted)",
                    "type": "table-context",
                    "summary": (
                        "GOVERNANCE RULE: Never expose email, phone_number, or home_address to "
                        "dashboards or agents. Always query through MCP Toolbox's lookup_vip_orders_masked."
                    ),
                },
                "dataplex-types.global.descriptions": {
                    "fields": [
                        {"name": "customer_id", "description": "Primary key customer ID."},
                        {"name": "full_name", "description": "Customer name (must be abbreviated to First Name + Last Initial in dashboards)."},
                        {"name": "email", "description": "RESTRICTED PII: Never select in agent or dashboard queries."},
                        {"name": "phone_number", "description": "RESTRICTED PII: Never select in agent or dashboard queries."},
                        {"name": "home_address", "description": "RESTRICTED PII: Never select in agent or dashboard queries."},
                        {"name": "loyalty_tier", "description": "Membership tier: BRONZE, SILVER, or GOLD."},
                    ]
                },
            },
        },
    ]


def build_schema_join_links(cfg: KnowledgeCatalogConfig) -> list[dict[str, Any]]:
    """Build `upsert_entry_link` payloads for approved joins and glossary definitions."""
    base_group = (
        f"projects/{cfg.project_id}/locations/{cfg.location}/entryGroups/{cfg.entry_group_id}"
    )

    return [
        {
            "name": f"{base_group}/entryLinks/def-net-revenue-to-orders",
            "entryLinkType": "projects/dataplex-types/locations/global/entryLinkTypes/definition",
            "allowMissing": True,
            "entryReferences": [
                {
                    "name": f"{base_group}/entries/glossary-net-store-revenue",
                    "type": "SOURCE",
                },
                {
                    "name": f"{base_group}/entries/table-orders-context",
                    "path": "Schema.gross_amount_usd",
                    "type": "TARGET",
                },
            ],
        },
        {
            "name": f"{base_group}/entryLinks/join-orders-to-customers",
            "entryLinkType": "projects/dataplex-types/locations/global/entryLinkTypes/schema-join",
            "allowMissing": True,
            "entryReferences": [
                {
                    "name": f"{base_group}/entries/table-orders-context",
                    "path": "Schema.customer_id",
                    "type": "UNSPECIFIED",
                },
                {
                    "name": f"{base_group}/entries/table-customers-context",
                    "path": "Schema.customer_id",
                    "type": "UNSPECIFIED",
                },
            ],
        },
    ]


def build_bigquery_property_graph_ddl(project_id: str, dataset_id: str = "chai_and_co") -> dict[str, str]:
    """Gap 4 Fix: Build BigQuery Property Graph DDL (`CREATE PROPERTY GRAPH`) and ISO GQL query.

    Connects Supplier -> TeaInventory -> Store <- Order <- Customer as a Knowledge Graph
    so agents can traverse multi-hop supply chain impacts without writing fragile 5-way SQL joins.
    """
    ddl = f"""CREATE OR REPLACE PROPERTY GRAPH `{project_id}.{dataset_id}.chai_supply_chain_graph`
  NODE TABLES (
    `{project_id}.{dataset_id}.suppliers`
      KEY (supplier_id)
      LABEL Supplier PROPERTIES (supplier_id, supplier_name, origin_region, shipment_status),
    `{project_id}.{dataset_id}.stores`
      KEY (store_id)
      LABEL Store PROPERTIES (store_id, store_name, city, manager_email),
    `{project_id}.{dataset_id}.customers`
      KEY (customer_id)
      LABEL Customer PROPERTIES (customer_id, loyalty_tier)
  )
  EDGE TABLES (
    `{project_id}.{dataset_id}.tea_inventory`
      KEY (store_id, sku_id)
      SOURCE KEY (supplier_id) REFERENCES suppliers (supplier_id)
      DESTINATION KEY (store_id) REFERENCES stores (store_id)
      LABEL SUPPLIES_STORE_SKU PROPERTIES (sku_id, item_name, stock_on_hand, reorder_threshold),
    `{project_id}.{dataset_id}.orders`
      KEY (order_id)
      SOURCE KEY (customer_id) REFERENCES customers (customer_id)
      DESTINATION KEY (store_id) REFERENCES stores (store_id)
      LABEL PLACED_ORDER_AT PROPERTIES (order_id, status, gross_amount_usd, discount_usd)
  );"""

    gql_query = f"""GRAPH `{project_id}.{dataset_id}.chai_supply_chain_graph`
MATCH (sup:Supplier {{shipment_status: 'DELAYED_MONSOON_FREIGHT'}})-[inv:SUPPLIES_STORE_SKU]->(s:Store)<-[ord:PLACED_ORDER_AT {{status: 'COMPLETED'}}]-(c:Customer)
WHERE inv.stock_on_hand <= inv.reorder_threshold
RETURN
  sup.supplier_name AS delayed_supplier,
  inv.item_name AS at_risk_tea_blend,
  s.store_name AS affected_store,
  COUNT(DISTINCT c.customer_id) AS impacted_vip_customers
GROUP BY delayed_supplier, at_risk_tea_blend, affected_store;"""

    return {"property_graph_ddl": ddl, "gql_traversal_query": gql_query}


def simulate_lookup_context_yaml(cfg: KnowledgeCatalogConfig) -> str:
    """Return the pre-formatted LLM-ready YAML context returned by `lookup_context`."""
    entries = build_glossary_and_table_entries(cfg)
    links = build_schema_join_links(cfg)
    context_summary = {
        "contextSet": f"projects/{cfg.project_id}/locations/{cfg.location}/entryGroups/{cfg.entry_group_id}",
        "governedMetrics": {
            "net_store_revenue": {
                "formula": "SUM(gross_amount_usd - discount_usd) FILTER (WHERE status = 'COMPLETED')",
                "excludedStatuses": ["REFUNDED", "CANCELLED"],
            },
            "at_risk_inventory": {
                "formula": "stock_on_hand <= reorder_threshold",
                "hiddenColumns": ["supplier_cost_usd"],
            },
        },
        "piiAndSafetyGovernance": {
            "customers": {
                "blockedColumns": ["email", "phone_number", "home_address"],
                "approvedMcpTool": "lookup_vip_orders_masked",
            },
            "orders_delivery_note": {
                "modelArmorTemplate": f"projects/{cfg.project_id}/locations/{cfg.location}/templates/chai-pii-and-jailbreak-shield",
                "enforcedFilters": ["SDP_PII_REDACTION", "INDIRECT_PROMPT_INJECTION"],
            },
        },
        "knowledgeGraph": f"projects/{cfg.project_id}/datasets/chai_and_co/propertyGraphs/chai_supply_chain_graph",
        "registeredEntriesCount": len(entries),
        "approvedJoinLinksCount": len(links),
    }
    return yaml.safe_dump(context_summary, sort_keys=False)


if __name__ == "__main__":
    config = KnowledgeCatalogConfig(project_id="chai-and-co-prod")
    print("=== Knowledge Catalog `lookup_context` YAML Summary ===")
    print(simulate_lookup_context_yaml(config))
