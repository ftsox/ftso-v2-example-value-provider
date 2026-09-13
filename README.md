# FTSOv2 Example Feed Value Provider

This is a sample implementation of an FTSOv2 feed value provider that serves values for requested feed IDs. By default, it uses [CCXT](https://ccxt.readthedocs.io/) to fetch the latest values from supported exchanges. Alternatively, it can be configured to provide fixed or random values for testing purposes.

## Running

Rebuild after any changes.
```bash
docker compose build
docker compose up -d
```

## Compare local and published provider prices

Place `compose.compare.yaml` and `compare_prices.py` in the repository root. Start the local build on port **4101** and the published GHCR image on port **4102**, using a separate Compose project:

```bash
docker compose -p feed-value-compare -f compose.compare.yaml pull feed-value-provider-ghcr
docker compose -p feed-value-compare -f compose.compare.yaml up -d --build
```

Compare all assets in `src/config/feeds.json` and save the results to CSV (requires Python 3; no extra packages):

```bash
python3 compare_prices.py --csv prices.csv
```

The script reports both prices and their differences, retrying missing prices for up to 60 seconds. Add `--wait 0` for an immediate snapshot. Prices can differ because the providers collect market data independently.

Stop and remove the comparison containers:

```bash
docker compose -p feed-value-compare -f compose.compare.yaml down
```


## Configuration

The provider behavior can be adjusted via the `VALUE_PROVIDER_IMPL` environment variable:
- `fixed`: returns a fixed value.
- `random`: returns random values.
- Leave blank to use the default CCXT-based values.

## Starting the Provider

To start the provider using Docker, run:

```bash
docker run --rm -it --publish "0.0.0.0:3101:3101" ghcr.io/flare-foundation/ftso-v2-example-value-provider
```

This will start the service on port `3101`. You can find the API spec at: http://localhost:3101/api-doc.

## Obtaining Feed Values

The provider exposes two API endpoints for retrieving feed values:

1. **`/feed-values/<votingRound>`**: Retrieves feed values for a specified voting round. Used by FTSOv2 Scaling clients.
2. **`/feed-values/`**: Retrieves the latest feed values without a specific voting round ID. Used by FTSOv2 Fast Updates clients.

> **Note**: In this example implementation, both endpoints return the same data, which is the latest feed values available.

### Example Usage

#### Fetching Feed Values with a Voting Round ID

Use the endpoint `/feed-values/<votingRound>` to obtain values for a specific voting round.

```bash
curl -X 'POST' \
  'http://localhost:3101/feed-values/0' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "feeds": [
    { "category": 1, "name" : "BTC/USD" }
  ]
}'
```

**Example Response:**

```json
{
  "votingRoundId": 0,
  "data": [
    { "feed": { "category": 1, "name": "BTC/USD" }, "value": 71287.34508311428 }
  ]
}
```

#### Fetching Latest Feed Values (Without Voting Round ID)

Use the endpoint `/feed-values/` to get the most recent feed values without specifying a voting round.

```bash
curl -X 'POST' \
  'http://localhost:3101/feed-values/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "feeds": [
    { "category": 1, "name" : "BTC/USD" }
  ]
}'
```

**Example Response:**

```json
{
  "data": [
    { "feed": { "category": 1, "name": "BTC/USD" }, "value": 71285.74004472858 }
  ]
}
```