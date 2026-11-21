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

Set `LLM_CHAT_URL` to an OpenAI-compatible chat completions endpoint reachable from the API, and set `LLM_MODEL` to a tool-capable model. Set `LLM_API_KEY` if the endpoint requires authentication. Send questions about the synthetic data to `POST /analyze` with a JSON body such as `{"question":"What was checkout conversion for the weeks starting November 2 and November 9, 2026?"}`.

The API validates the model's tool arguments against the approved checkout conversion query. It returns the DuckDB rows and a link that reruns the same filters against the current metric data. If the model selects no tool, the API asks for clarification.

Run `dbt build --profiles-dir .` and then `python evaluate.py` to check the API and evidence against the synthetic fixture with scripted model responses. The suite expects clarification for missing metric or date scope and unsupported signup conversion. It checks that duplicate purchases and purchases without a checkout start cannot inflate the approved metric, even when questions request those counting rules. Run `python evaluate.py --live` with the model settings above to measure tool selection by a live model.
