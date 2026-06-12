"""
buggy-service — a deliberately broken Lambda for the Patchwork demo.

The handler processes an incoming "order" event and computes a shipping
quote. It contains a REAL, diagnosable bug: it assumes every order has a
`customer.address`, but guest checkouts send `customer: null`. On that
input the function raises, and we log the full traceback as structured
JSON so the downstream Strands agent has genuine source + stack to work
from.

The bug, root cause, and fix hint are documented inline so we can later
verify the agent reached the right conclusion.
"""

import json
import logging
import traceback
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Flat shipping rates by destination tier. Anything not listed falls back
# to the "standard" rate.
SHIPPING_RATES = {
    "domestic": 4.99,
    "international": 19.99,
    "standard": 9.99,
}


def _resolve_rate(city: str) -> float:
    """Pick a shipping rate from the city name (toy logic for the demo)."""
    if city.lower() in ("london", "new york", "tokyo"):
        return SHIPPING_RATES["international"]
    return SHIPPING_RATES["domestic"]


# BUG B: parses the delivery date with a strict format and no error handling.
# ROOT CAUSE: a malformed date like "2026-13-40" (month 13, day 40) makes
#   datetime.strptime raise `ValueError: unconverted data` / `time data ... does
#   not match format`, crashing the order.
# FIX HINT: validate the date and reject/normalise bad input instead of letting
#   strptime raise.
def _eta_days(delivery_date: str) -> int:
    parsed = datetime.strptime(delivery_date, "%Y-%m-%d")
    return max(0, (parsed - datetime(2026, 6, 12)).days)


# BUG: reads `customer["address"]` without checking that `customer` exists.
# ROOT CAUSE: guest checkouts send `"customer": null`, so `order["customer"]`
#   is None and subscripting it raises `TypeError: 'NoneType' object is not
#   subscriptable`.
# FIX: guard for a missing/None customer and fall back to the standard rate.
def quote_shipping(order: dict) -> dict:
    customer = order.get("customer")
    if customer is None:
        order_id = order.get("id")
        logger.warning(
            json.dumps(
                {
                    "event": "quote.guest_checkout",
                    "message": "customer is null; falling back to standard shipping rate",
                    "orderId": order_id,
                }
            )
        )
        rate = SHIPPING_RATES["standard"]
        city = None
    else:
        city = customer["address"]["city"]
        rate = _resolve_rate(city)
    eta = _eta_days(order.get("deliveryDate", "2026-06-20"))
    return {
        "orderId": order.get("id"),
        "city": city,
        "shipping": rate,
        "etaDays": eta,
    }


def handler(event, context):
    """Lambda entry point.

    Expects an event shaped like:
        {"id": "ord_42", "customer": {"address": {"city": "London"}}}

    Guest checkouts arrive as:
        {"id": "ord_43", "customer": null}   <-- previously triggered the bug
    """
    # API Gateway delivers the order in `body` as a JSON string; direct
    # invocations pass the order as the event itself.
    if isinstance(event, dict) and "body" in event:
        order = json.loads(event["body"]) if event["body"] else {}
    else:
        order = event or {}

    logger.info(json.dumps({"event": "quote.request", "order": order}))

    try:
        quote = quote_shipping(order)
    except Exception as err:  # noqa: BLE001 — we want every failure logged
        logger.error(
            json.dumps(
                {
                    "event": "quote.error",
                    "errorType": type(err).__name__,
                    "message": str(err),
                    "source": "lambda/buggy_service/handler.py",
                    "function": "quote_shipping",
                    "stack": traceback.format_exc(),
                    "order": order,
                }
            )
        )
        # Re-raise so the failure also shows up as a Lambda error/metric,
        # not just a log line.
        raise

    return {
        "statusCode": 200,
        "body": json.dumps(quote),
    }
