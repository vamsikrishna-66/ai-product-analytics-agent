import os
from datetime import date
from typing import Annotated

import duckdb
from fastapi import FastAPI, HTTPException
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
