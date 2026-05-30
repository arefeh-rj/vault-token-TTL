# Vault Token TTL Exporter

This project extracts token TTL information from HashiCorp Vault APIs and exposes them as Prometheus metrics.

## Background

Because ``` root token ``` access was not available, it was not possible to directly retrieve all token details from Vault directly.
To work around this limitation, two Vault APIs are called sequentially:

1. List all token accessors
2. Lookup each accessor individually to retrieve its TTL

## APIs Used

### 1. List Token Accessors

```http
GET {vault_addr}/v1/auth/token/accessors?list=true
```

This endpoint returns the list of token accessors.

### 2. Lookup Token Accessor

```http
POST {vault_addr}/v1/auth/token/lookup-accessor
```

Each accessor retrieved from the first API is sent to this endpoint to fetch detailed token information, including TTL.

## Workflow

1. Fetch all token accessors from Vault
2. Iterate through the accessor list
3. Call the lookup API for each accessor
4. Extract TTL values
5. Convert the results into Prometheus metrics
6. Expose metrics on the configured port

## Configuration Parameters
> firstly `vault_nodes` contains multiple Vault nodes because the exporter first detects the active leader node in the HA cluster before performing token accessor operations.

| Parameter                 | Description                                          |
| ------------------------- | ---------------------------------------------------- |
| `vault_nodes`             | List of Vault nodes to scrape                        |
| `vault_token`             | Vault token with minimum required policy permissions |
| `scrape_port`             | Port used to expose Prometheus metrics               |
| `scrape_interval`         | Interval (in seconds) between Vault scrapes          |
| `alert_threshold_minutes` | Threshold used for detecting near-expired tokens     |

## Run

Before running the exporter, make sure to update the configuration section in the source file based on your environment.

You can either run the exporter directly using:

```bash id="8v4js5"
python vault_metrics.py
```

or build and run it using Docker based on your deployment requirements:

```bash id="w9v9kc"
docker build -t vault-token-exporter .
docker run -p 8000:8000 vault-token-exporter
```


## Metrics

Metrics will be available on the configured port under the ``` /metrics ``` endpoint.
Example metric format:

```text
vault_token_ttl_seconds{accessor="xxxx"} 3600
```

## Use Cases

* Monitoring token expiration
* Detecting stale or long-lived tokens
* Integrating Vault token visibility into Prometheus/Grafana
* Creating alerts for tokens close to expiration
