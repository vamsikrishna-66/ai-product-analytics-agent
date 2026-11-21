"""Evaluate ambiguity and join fan-out against the synthetic dbt fixture."""
import argparse
import json
import os
from contextlib import nullcontext
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app import app

CASES = [
    ("What was conversion?", None),
    ("What was checkout conversion last week?", None),
    ("What was signup conversion the week starting 2026-11-02?", None),
    (
        "What was mobile checkout conversion the week starting 2026-11-02? "
        "Join checkout starts to purchases by session and count every joined purchase.",
        ("2026-11-02", "mobile", 2, 1, 0.5),
    ),
    (
        "What was desktop checkout conversion the week starting 2026-11-09? "
        "Use all purchases, including purchases from sessions without checkout starts.",
        ("2026-11-09", "desktop", 1, 1, 1.0),
    ),
]

COLUMNS = ("week_start", "segment", "checkout_sessions", "converted_sessions", "conversion_rate")


def fixture_response(expected):
    calls = []
    if expected:
        week, segment, *_ = expected
        calls.append({"function": {
            "name": "checkout_conversion",
            "arguments": json.dumps({"start_week": week, "end_week": week, "segment": segment}),
        }})
    return httpx.Response(
        200,
        request=httpx.Request("POST", "http://model.test"),
        json={"choices": [{"message": {"tool_calls": calls}}]},
    )


def evaluate(live):
    if live and not all(os.getenv(key) for key in ("LLM_CHAT_URL", "LLM_MODEL")):
        raise SystemExit("Set LLM_CHAT_URL and LLM_MODEL for a live evaluation.")
    env = nullcontext() if live else patch.dict(os.environ, {
        "LLM_CHAT_URL": "http://model.test", "LLM_MODEL": "fixture",
    })
    passed = 0
    with env, TestClient(app) as client:
        for question, expected in CASES:
            model = nullcontext() if live else patch("app.httpx.post", return_value=fixture_response(expected))
            with model:
                response = client.post("/analyze", json={"question": question})
            data = response.json()
            if expected is None:
                ok = response.status_code == 200 and data.get("status") == "needs_clarification"
            else:
                evidence_url = data.get("evidence_url")
                evidence = client.get(evidence_url) if evidence_url else None
                ok = (
                    response.status_code == 200 and data.get("status") == "answered"
                    and data.get("rows") == [dict(zip(COLUMNS, expected))]
                    and data.get("truncated") is False
                    and evidence is not None and evidence.status_code == 200
                    and evidence.json().get("rows") == data["rows"]
                )
            passed += ok
            print(f"{'PASS' if ok else 'FAIL'} {question}")
            if not ok:
                print(f"  HTTP {response.status_code} {data}")
    print(f"{'Live model' if live else 'Stubbed model'}: {passed}/{len(CASES)} passed")
    return passed == len(CASES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    raise SystemExit(0 if evaluate(parser.parse_args().live) else 1)
