# Dataset Schema: ManikaSaini/zomato-restaurant-recommendation

Source: [Hugging Face](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)  
Split: `train` (~51,717 rows)

## Raw columns → canonical mapping

| Raw column | Type | Canonical field | Notes |
|------------|------|-----------------|-------|
| `url` | string | `id` | SHA-256 hash prefix of URL |
| `name` | string | `name` | Required; rows without name dropped |
| `listed_in(city)` | string | `location` | Preferred city (normalized, lowercased) |
| `location` | string | `metadata.locality` | Area/locality fallback for location |
| `cuisines` | string | `cuisines[]` | Split on `,` `\|` `/` |
| `rate` | string | `rating` | Parse `4.1/5`; drop `NEW`, `-`, empty |
| `approx_cost(for two people)` | string | `cost` | Strip `₹`, commas; average if range |
| `votes` | int | `metadata.votes` | Optional |
| `address` | string | `metadata.address` | Optional |
| `rest_type` | string | `metadata.rest_type` | Optional |
| `online_order` | string | `metadata.online_order` | Optional |
| `book_table` | string | `metadata.book_table` | Optional |

## Derived fields

| Field | Derivation |
|-------|------------|
| `budget_tier` | Percentiles (33/66) on valid `cost` values: `low`, `medium`, `high` |
| `id` | `sha256(url)[:16]` or `sha256(name:index)[:16]` |

## Rows dropped during ingestion

- Missing `name`
- Missing both city (`listed_in(city)`) and `location`
- Unparseable `rate` (`NEW`, `-`, empty, out of range)

## Location normalization

Synonym map applied after lowercasing:

| Input | Normalized |
|-------|------------|
| Bengaluru | bangalore |
| New Delhi | delhi |
| Delhi NCR | delhi |
