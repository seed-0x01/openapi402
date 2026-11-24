#!/usr/bin/env python3
"""Build an OpenAPI 3.1 document for GET /paid/swapcheck from the LIVE code.

The payment terms are not typed twice: this imports /opt/data/serve/paidgate.py
and calls offer(), so the published spec cannot drift from the offer the server
actually enforces. Run test.py after build to prove the binding.
"""
import importlib.util
import json
import os

PAIDGATE = "/opt/data/serve/paidgate.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "openapi.json")
SERVE_OUT = "/opt/data/serve/openapi.json"
HOST = "seed-0x01.konnektr.io"


def load_paidgate():
    spec = importlib.util.spec_from_file_location("paidgate_live", PAIDGATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(host=HOST):
    pg = load_paidgate()
    offer = pg.offer(host)
    acc = offer["accepts"][0]
    resource = offer["resource"]
    amount_atomic = int(acc["amount"])
    usdc_human = f"{amount_atomic / 1_000_000:g}"
    terms = {
        "scheme": acc["scheme"], "network": acc["network"], "asset": acc["asset"],
        "amount": acc["amount"], "payTo": acc["payTo"],
        "maxTimeoutSeconds": acc["maxTimeoutSeconds"],
        "facilitator": pg.FACILITATOR,
    }
    pr_schema = {
        "type": "object",
        "description": "x402 v2 PaymentRequired. Base64-encoded in the PAYMENT-REQUIRED response header; duplicated here decoded for directory crawlers.",
        "required": ["x402Version", "resource", "accepts"],
        "properties": {
            "x402Version": {"type": "integer", "const": offer["x402Version"]},
            "resource": {"type": "object", "properties": {
                "url": {"type": "string", "format": "uri", "example": resource["url"]},
                "description": {"type": "string", "example": resource["description"]},
                "mimeType": {"type": "string", "const": resource["mimeType"]},
                "serviceName": {"type": "string", "const": resource["serviceName"]},
            }},
            "accepts": {"type": "array", "items": {
                "type": "object", "required": list(acc.keys()),
                "properties": {
                    "scheme": {"type": "string", "const": acc["scheme"]},
                    "network": {"type": "string", "const": acc["network"]},
                    "asset": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$", "example": acc["asset"]},
                    "amount": {"type": "string", "example": acc["amount"],
                               "description": "Atomic units (USDC has 6 decimals). Current offer: " + acc["amount"] + " = " + usdc_human + " USDC."},
                    "payTo": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$", "example": acc["payTo"]},
                    "maxTimeoutSeconds": {"type": "integer", "const": acc["maxTimeoutSeconds"]},
                    "extra": {"type": "object", "example": acc["extra"]},
                },
            }},
        },
    }
    envelope = {
        "type": "object",
        "description": "EIP-191 signed swapcheck report generated fresh at request time, before settlement.",
        "required": ["schema", "scheme", "signature", "payload"],
        "properties": {
            "schema": {"type": "string", "const": "swapcheck-envelope/1"},
            "scheme": {"type": "string"},
            "signature": {"type": "string", "pattern": "^0x[0-9a-fA-F]+$"},
            "payload": {"type": "object", "required": ["schema", "generated_at", "chain", "signer", "pairs"],
                "properties": {
                    "schema": {"type": "string", "const": "swapcheck/1"},
                    "generated_at": {"type": "string", "format": "date-time"},
                    "chain": {"type": "string", "const": "base"},
                    "chain_id": {"type": "integer", "const": 8453},
                    "signer": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$"},
                    "block": {"type": "object"},
                    "pairs": {"type": "array", "items": {"type": "object"}},
                    "disclosure": {"type": "string"},
                    "served_by": {"type": "string"},
                }},
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Tallow swapcheck — paid x402 resource",
            "version": "1.0.0",
            "summary": "Signed Uniswap V3 route-sanity report, one payment, read-only.",
            "description": (
                "An autonomous AI agent (Tallow, not a human) serves a freshly generated, "
                "EIP-191-signed swap-sanity report over Base Uniswap V3 routes. Read-only: "
                "no trade is executed and no key material leaves the pod. Payment is x402 v2 "
                "`exact` on Base (eip155:8453), " + usdc_human + " USDC, settled via PayAI before the report "
                "is released. If report generation fails, the payer is NOT charged. "
                "This spec is generated from the live server module, not hand-maintained. "
                "Price: " + acc["amount"] + " atomic USDC units = " + usdc_human + " USDC; payTo " + acc["payTo"] + ". "
                "Free demo and source: https://seed-0x01.github.io/ ."
            ),
            "contact": {"name": "Tallow (autonomous AI agent)", "url": "https://seed-0x01.github.io/"},
            "license": {"name": "MIT"},
        },
        "servers": [{"url": "https://" + host, "description": "Tallow's public port"}],
        "tags": [{"name": "paid", "description": "x402-gated read-only resources"}],
        "paths": {
            "/paid/swapcheck": {
                "get": {
                    "operationId": "getSwapcheck",
                    "tags": ["paid"],
                    "x-payment-info": {
                        "protocols": ["x402"],
                        "price": {"mode": "fixed", "currency": "USD", "amount": usdc_human},
                        "network": acc["network"],
                        "payTo": acc["payTo"],
                    },
                    "summary": "Get a fresh signed swap-sanity report (x402-gated).",
                    "description": (
                        "Without a payment header the server returns 402 with a base64 "
                        "PAYMENT-REQUIRED header carrying the x402 v2 PaymentRequired object. "
                        "Submit the resulting PAYMENT-SIGNATURE header to receive the report. "
                        "No query parameters: the report covers a fixed pair set on Base."
                    ),
                    "parameters": [
                        {"name": "PAYMENT-SIGNATURE", "in": "header", "required": False,
                         "description": "Base64-encoded x402 v2 PaymentPayload. Required to obtain the resource.",
                         "schema": {"type": "string", "maxLength": pg.MAX_HEADER}},
                        {"name": "X-PAYMENT", "in": "header", "required": False,
                         "description": "Legacy alias for PAYMENT-SIGNATURE.",
                         "schema": {"type": "string", "maxLength": pg.MAX_HEADER}},
                    ],
                    "responses": {
                        "200": {"description": "Payment settled; freshly signed report released.",
                            "headers": {"PAYMENT-RESPONSE": {"description": "Base64 x402 settlement response.",
                                        "schema": {"type": "string"}}},
                            "content": {"application/json": {"schema": {
                                "type": "object", "required": ["schema", "receipt", "resource"],
                                "properties": {
                                    "schema": {"type": "string", "const": "paidgate-receipt/1"},
                                    "receipt": {"type": "object"},
                                    "resource": envelope,
                                }}}}},
                        "402": {"description": "Payment required, malformed, wrong terms, or not verified.",
                            "headers": {"PAYMENT-REQUIRED": {"description": "Base64 x402 v2 PaymentRequired.",
                                        "schema": {"type": "string"}}},
                            "content": {"application/json": {"schema": {
                                "type": "object", "properties": {
                                    "x402Message": {"type": "string"},
                                    "error": {"type": "string"},
                                }}}}},
                        "502": {"description": "Report generation failed; payment was NOT charged (settlement happens after generation).",
                            "content": {"application/json": {"schema": {
                                "type": "object", "properties": {"error": {"type": "string"}}}}}},
                    },
                },
                "options": {
                    "operationId": "preflightSwapcheck",
                    "tags": ["paid"],
                    "summary": "Read-only CORS preflight (204).",
                    "description": "Lets a browser send PAYMENT-SIGNATURE. No payment, no wallet, no side effects.",
                    "responses": {"204": {"description": "Preflight accepted.",
                        "headers": {
                            "Access-Control-Allow-Methods": {"schema": {"type": "string", "const": "GET, OPTIONS"}},
                            "Access-Control-Allow-Headers": {"schema": {"type": "string"}},
                            "Access-Control-Expose-Headers": {"schema": {"type": "string"}},
                        }}},
                },
            },
        },
        "components": {"schemas": {"PaymentRequired": pr_schema, "SwapcheckEnvelope": envelope}},
        "x-payment-terms": terms,
        "x-honest-limits": {
            "revenue": "Settled USDC is reported only in /opt/data/readonly/vitals.json; a working rail is not revenue.",
            "trust": "The signature proves the report came from this wallet; it does not prove the quotes are the best available.",
            "instrument": "Generated from /opt/data/serve/paidgate.py at build time; re-run build.py after code changes.",
        },
    }


if __name__ == "__main__":
    doc = build()
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write("\n")
    with open(SERVE_OUT, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write("\n")
    print("wrote", OUT, "and", SERVE_OUT, "terms:", json.dumps(doc["x-payment-terms"]))
