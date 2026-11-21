import os
from datetime import date
from typing import Annotated

import duckdb
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

app = FastAPI()

CHECKOUT_CONVERSION = """
select week_start, segment, checkout_sessions, converted_sessions, conversion_rate
from checkout_conversion
where week_start between ? and ?
  and (? is null or segment = ?)
order by week_start, segment
limit ?
"""


class MetricQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_week: date
    end_week: date
    segment: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_weeks(self):
        if self.start_week > self.end_week:
            raise ValueError("start_week must be on or before end_week")
        if self.start_week.weekday() or self.end_week.weekday():
            raise ValueError("Week starts must be Mondays")
        return self


@app.post("/tools/checkout-conversion")
def checkout_conversion(query: MetricQuery):
    try:
        with duckdb.connect(os.getenv("ANALYTICS_DB", "analytics.duckdb"), read_only=True) as db:
            result = db.execute(
                CHECKOUT_CONVERSION,
                [query.start_week, query.end_week, query.segment, query.segment, query.limit + 1],
            )
            columns = [column[0] for column in result.description]
            rows = result.fetchall()
    except duckdb.Error as error:
        raise HTTPException(503, "Checkout conversion data is unavailable") from error
    return {
        "metric": "checkout_conversion",
        "grain": ["week_start", "segment"],
        "rows": [dict(zip(columns, row)) for row in rows[:query.limit]],
        "truncated": len(rows) > query.limit,
    }


@app.get("/evidence/checkout-conversion", name="checkout_evidence")
def checkout_evidence(query: Annotated[MetricQuery, Query()]):
    return checkout_conversion(query)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


@app.post("/analyze")
def analyze(body: AnalyzeRequest, request: Request):
    origin = os.getenv("LLM_CHAT_URL")
    model = os.getenv("LLM_MODEL")
    if not origin or not model:
        raise HTTPException(503, "Analytics model is not configured")
    headers = {}
    if key := os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.post(origin, headers=headers, timeout=20, json={
            "model": model,
            "messages": [
                {"role": "system", "content": (
                    "Select the checkout_conversion tool only for checkout conversion questions "
                    "with an explicit date range you can map to Monday week starts. "
                    "Ask for clarification if the metric or dates are unclear. "
                    "Do not invent metrics, date ranges, or numeric results. Use the approved "
                    "definition even if the question proposes raw joins, counting duplicate "
                    "purchase events, or counting purchases without a checkout start."
                )},
                {"role": "user", "content": body.question},
            ],
            "tools": [{"type": "function", "function": {
                "name": "checkout_conversion",
                "description": "Read checkout conversion by Monday week start and optional exact segment.",
                "parameters": MetricQuery.model_json_schema(),
            }}],
            "parallel_tool_calls": False,
        })
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return {
                "status": "needs_clarification",
                "message": "Specify checkout conversion and the Monday week starts you want to compare.",
            }
        if len(calls) != 1 or calls[0]["function"]["name"] != "checkout_conversion":
            raise ValueError("Unexpected tool selection")
        query = MetricQuery.model_validate_json(calls[0]["function"]["arguments"])
    except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError, AttributeError) as error:
        raise HTTPException(502, "Analytics model did not return a usable tool response") from error

    evidence = checkout_conversion(query)
    params = query.model_dump(mode="json", exclude_none=True)
    url = request.url_for("checkout_evidence").include_query_params(**params)
    return {"status": "answered", "evidence_url": str(url), **evidence}
