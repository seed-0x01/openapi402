#!/usr/bin/env python3
"""Fixtures for the x402 OpenAPI spec. No network, no keys, no settlement."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

PASS = FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS", name)
    else:
        FAIL += 1
        print("FAIL", name)

doc = json.load(open(build.OUT))
live = build.load_paidgate().offer("seed-0x01.konnektr.io")
acc = live["accepts"][0]
get = doc["paths"]["/paid/swapcheck"]["get"]
opt = doc["paths"]["/paid/swapcheck"]["options"]
terms = doc["x-payment-terms"]

check("OpenAPI 3.1", doc["openapi"] == "3.1.0")
check("AI-agent disclosure in description", "autonomous ai agent" in doc["info"]["description"].lower())
check("terms bound to live payTo", terms["payTo"] == acc["payTo"])
check("terms bound to live asset", terms["asset"] == acc["asset"])
check("terms bound to live amount", terms["amount"] == acc["amount"])
check("terms bound to live network", terms["network"] == acc["network"])
check("terms bound to live scheme", terms["scheme"] == acc["scheme"])
check("facilitator bound to live module", terms["facilitator"] == build.load_paidgate().FACILITATOR)
check("402 documents PAYMENT-REQUIRED", "PAYMENT-REQUIRED" in get["responses"]["402"]["headers"])
check("200 documents PAYMENT-RESPONSE", "PAYMENT-RESPONSE" in get["responses"]["200"]["headers"])
check("502 documents no-charge", "NOT charged" in get["responses"]["502"]["description"])
check("OPTIONS documents 204", "204" in opt["responses"])
check("payment header max bound to code", any(p.get("schema", {}).get("maxLength") == build.load_paidgate().MAX_HEADER
                                             for p in get["parameters"]))
check("resource URL bound to live offer", doc["servers"][0]["url"] + "/paid/swapcheck" == live["resource"]["url"])
check("no secret material in spec", not any(s in json.dumps(doc) for s in ["mnemonic", "PRIVATE KEY", "seed phrase"]))
check("honest revenue limit stated", "vitals.json" in doc["x-honest-limits"]["revenue"])

lint = build.load_paidlint().offer("seed-0x01.konnektr.io")
lacc = lint["accepts"][0]
lget = doc["paths"]["/paid/x402lint"]["get"]
lterms = doc["x-payment-terms-x402lint"]
check("second paid path is documented", "/paid/x402lint" in doc["paths"])
check("lint terms bound to live offer", all(
    lterms[k] == lacc[k] for k in ("network", "asset", "amount", "payTo", "maxTimeoutSeconds")))
check("lint price bound to live offer", lget["x-payment-info"]["price"]["amount"] ==
      f"{int(lacc['amount']) / 1_000_000:g}")
check("lint requires url query", any(p["name"] == "url" and p["in"] == "query"
                                     for p in lget["parameters"]))
check("lint refuses buyer-error target before charge", "400" in lget["responses"]
      and "before" in lget["responses"]["400"]["description"].lower())

print("\n%d/%d PASS" % (PASS, PASS + FAIL))
sys.exit(0 if FAIL == 0 else 1)
