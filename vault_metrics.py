import os
import time
import requests
from datetime import datetime, timezone
import yaml
from prometheus_client import start_http_server, Gauge

# ----------------------------
# CONFIGURATION
# ----------------------------
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.yml")

with open(CONFIG_FILE, "r") as f:
    config = yaml.safe_load(f)

VAULT_NODES = config.get("vault_nodes", [])
VAULT_TOKEN = config.get("vault_token")
SCRAPE_PORT = config.get("scrape_port", 8000)
SCRAPE_INTERVAL = config.get("scrape_interval", 30)
ALERT_THRESHOLD_MINUTES = config.get("alert_threshold_minutes", 5)

if not VAULT_TOKEN:
    raise Exception("VAULT_TOKEN not set in config!")

HEADERS = {"X-Vault-Token": VAULT_TOKEN}

# Prometheus metric: TTL of each token in seconds
token_ttl_gauge = Gauge(
    "vault_token_ttl_seconds",
    "TTL in seconds of Vault tokens",
    ["display_name", "accessor", "policies"]
)

# ----------------------------
# VAULT HELPER FUNCTIONS
# ----------------------------
def find_leader(nodes):
    """Find the current Vault leader among the given nodes."""
    for node in nodes:
        try:
            resp = requests.get(f"{node}/v1/sys/leader", timeout=2 , proxies={"http": None, "https": None})
            resp.raise_for_status()
            data = resp.json()
            if data.get("is_self", False):
                return node
        except Exception as e:
            print(f"Node {node} not reachable: {e}")
    raise Exception("No leader found")

def list_accessors(vault_addr):
    """Return a list of all token accessors."""
    url = f"{vault_addr}/v1/auth/token/accessors?list=true"
    resp = requests.get(url, headers=HEADERS, proxies={"http": None, "https": None})
    resp.raise_for_status()
    return resp.json().get("data", {}).get("keys", [])

def lookup_accessor(vault_addr, accessor):
    """Return token info for a given accessor."""
    url = f"{vault_addr}/v1/auth/token/lookup-accessor"
    resp = requests.post(url, headers=HEADERS, proxies={"http": None, "https": None}, json={"accessor": accessor})
    resp.raise_for_status()
    return resp.json()["data"]

def check_ttl_and_alert(token_info):
    """Check TTL, update Prometheus metrics, and print alerts."""
    display_name = token_info.get("display_name", "unknown")
    accessor = token_info.get("accessor", "unknown")
    ttl_seconds = token_info.get("ttl", 0)
    expire_time_raw = token_info.get("expire_time")

    expire_time = None
    if expire_time_raw:
        if isinstance(expire_time_raw, str):
            expire_time = datetime.fromisoformat(expire_time_raw.replace("Z", "+00:00"))
            ttl_seconds = int((expire_time - datetime.now(timezone.utc)).total_seconds())
        else:
            expire_time = datetime.fromtimestamp(expire_time_raw, tz=timezone.utc)

    policies_str = ",".join(token_info.get("policies", []))

    # Update Prometheus metric
    token_ttl_gauge.labels(
        display_name=display_name,
        accessor=accessor,
        policies=policies_str
    ).set(ttl_seconds)

    expire_str = expire_time.isoformat() if expire_time else "never"
    print(f"Token '{display_name}' (accessor {accessor}, policies={policies_str}) TTL={ttl_seconds}s, expires at {expire_str}")

    if ttl_seconds > 0 and ttl_seconds <= ALERT_THRESHOLD_MINUTES * 60:
        print(f"⚠️ ALERT: Token '{display_name}' is expiring soon! TTL={ttl_seconds}s")

# ----------------------------
# MAIN LOOP
# ----------------------------
start_http_server(SCRAPE_PORT)
print(f"Prometheus metrics available at http://127.0.0.1:{SCRAPE_PORT}/metrics")

while True:
    try:
        VAULT_ADDR = find_leader(VAULT_NODES)
        print(f"\nUsing Vault leader at {VAULT_ADDR}")
        accessors = list_accessors(VAULT_ADDR)
        token_ttl_gauge.clear()
        print(f"Found {len(accessors)} token accessors at {datetime.now(timezone.utc)}")

        for accessor in accessors:
            try:
                token_info = lookup_accessor(VAULT_ADDR, accessor)
                check_ttl_and_alert(token_info)
            except Exception as e:
                print(f"Error fetching token {accessor}: {e}")
    except Exception as e:
        print(f"Error finding leader or listing accessors: {e}")

    time.sleep(SCRAPE_INTERVAL)