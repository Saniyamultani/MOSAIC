"""Turn extracted fields into Life Graph node/edge specs.

Shared by every LLM provider so the graph shape is identical whether Gemini or
the offline extractor produced the fields.
"""
from __future__ import annotations

from datetime import date

from .. import textutils as T

NodeSpec = dict
EdgeSpec = dict


def _node(type: str, name: str, **attributes) -> NodeSpec:
    return {
        "type": type,
        "name": str(name).strip(),
        "attributes": {k: v for k, v in attributes.items() if v not in (None, "", [])},
    }


def _edge(source: str, target: str, type: str, **attributes) -> EdgeSpec:
    return {"source": source, "target": target, "type": type, "attributes": attributes}


def build_graph_payload(kind: str, fields: dict) -> tuple[list[NodeSpec], list[EdgeSpec]]:
    nodes: list[NodeSpec] = []
    edges: list[EdgeSpec] = []

    def add(node: NodeSpec | None) -> str | None:
        if node is None or not node["name"]:
            return None
        for existing in nodes:
            if existing["type"] == node["type"] and T.normalize_key(
                existing["name"]
            ) == T.normalize_key(node["name"]):
                existing["attributes"].update(node["attributes"])
                return existing["name"]
        nodes.append(node)
        return node["name"]

    brand = fields.get("brand") or fields.get("provider")
    payment = fields.get("payment_method")

    if kind in ("receipt", "note", "warranty", "calendar_event"):
        product_name = fields.get("product") or fields.get("related_product")
        product = None
        if product_name:
            product = add(
                _node(
                    "product",
                    product_name,
                    brand=brand,
                    model=fields.get("model"),
                    model_code=fields.get("model_code"),
                    model_codes=fields.get("model_codes"),
                    category=fields.get("category"),
                    price=fields.get("price"),
                    currency=fields.get("currency"),
                    purchase_date=fields.get("purchase_date") or fields.get("start_date"),
                    seller=fields.get("seller"),
                )
            )
        brand_node = add(_node("brand", brand) if brand else None)
        seller_node = add(_node("retailer", fields["seller"]) if fields.get("seller") else None)
        pay_node = add(_node("payment_method", payment) if payment else None)

        if product and brand_node:
            edges.append(_edge(product, brand_node, "MANUFACTURED_BY"))
        if product and seller_node:
            edges.append(
                _edge(product, seller_node, "PURCHASED_FROM",
                      purchase_date=fields.get("purchase_date"))
            )
        if product and pay_node:
            edges.append(_edge(product, pay_node, "PAID_WITH"))

        expiry = fields.get("expiry_date")
        months = fields.get("warranty_months") or fields.get("duration_months")
        start = fields.get("start_date") or fields.get("purchase_date")
        if not expiry and months and start:
            try:
                expiry = T.add_months(date.fromisoformat(start), int(months)).isoformat()
            except (ValueError, TypeError):
                expiry = None
        if product and (kind == "warranty" or expiry or months):
            warranty_node = add(
                _node(
                    "warranty",
                    f"{product} warranty",
                    provider=fields.get("provider") or brand,
                    start_date=start,
                    expiry_date=expiry,
                    duration_months=months,
                )
            )
            edges.append(_edge(product, warranty_node, "COVERED_BY", expires_on=expiry))
            if brand_node:
                edges.append(_edge(warranty_node, brand_node, "PROVIDED_BY"))

        if kind == "calendar_event" and fields.get("event_title"):
            event = add(
                _node("event", fields["event_title"], event_date=fields.get("event_date"))
            )
            if product:
                edges.append(_edge(event, product, "RELATES_TO"))

    elif kind == "subscription":
        name = fields.get("subscription_name") or fields.get("provider") or "Subscription"
        sub = add(
            _node(
                "subscription",
                name,
                amount=fields.get("amount") or fields.get("price"),
                currency=fields.get("currency"),
                billing_cycle=fields.get("billing_cycle"),
                renewal_date=fields.get("renewal_date"),
                provider=fields.get("provider"),
            )
        )
        provider_node = add(_node("brand", fields["provider"]) if fields.get("provider") else None)
        pay_node = add(_node("payment_method", payment) if payment else None)
        if sub and provider_node and T.normalize_key(sub) != T.normalize_key(provider_node):
            edges.append(_edge(sub, provider_node, "PROVIDED_BY"))
        if sub and pay_node:
            edges.append(_edge(sub, pay_node, "PAID_WITH"))

    elif kind == "bill":
        biller = fields.get("biller") or brand or "Bill"
        bill = add(
            _node(
                "bill",
                f"{biller} bill",
                amount=fields.get("amount") or fields.get("price"),
                currency=fields.get("currency"),
                due_date=fields.get("due_date"),
                category=fields.get("category"),
            )
        )
        biller_node = add(_node("brand", biller))
        pay_node = add(_node("payment_method", payment) if payment else None)
        if bill and biller_node:
            edges.append(_edge(bill, biller_node, "ISSUED_BY"))
        if bill and pay_node:
            edges.append(_edge(bill, pay_node, "PAID_WITH"))

    return nodes, edges
