# AI Product Analytics Agent

Day 1 defines checkout conversion on a deterministic synthetic event dataset. A session converts when it contains both a checkout start and a purchase in the same week and segment. Duplicate purchases count once, and purchases without a checkout start do not enter the numerator or denominator.

DuckDB runs the metric locally. dbt ties the CSV seed, metric model, and expected-output test into one repeatable build.

```sh
docker compose run --build --rm metrics
```

Next milestones expose approved metric queries through FastAPI, connect them to an LLM through structured tool calls, and evaluate answers against known results.
