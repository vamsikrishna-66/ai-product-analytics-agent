# AI Product Analytics Agent

The dbt model defines checkout conversion on a deterministic synthetic event dataset. A session converts when it contains both a checkout start and a purchase in the same week and segment. Duplicate purchases count once, and purchases without a checkout start do not enter the numerator or denominator.

DuckDB runs the metric locally. dbt ties the CSV seed, metric model, and expected-output test into one repeatable build.

```sh
docker compose run --build --rm metrics
```

Run the API against the built metrics with `docker compose up --build api`.

```sh
curl http://localhost:8000/tools/checkout-conversion \
  -H 'Content-Type: application/json' \
  -d '{"start_week":"2026-11-02","end_week":"2026-11-09","limit":100}'
```

The tool accepts an inclusive range of Monday week starts, an optional exact segment, and a row limit between 1 and 500. It executes a fixed parameterized query against a read-only DuckDB connection and returns rows at week and segment grain. A true `truncated` flag indicates the result exceeded the requested limit.
