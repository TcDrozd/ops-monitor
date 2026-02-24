# API Endpoints

Base URL examples below use:

```bash
BASE_URL="http://127.0.0.1:8060"
```

## GET /health

Process liveness endpoint.

Example:

```bash
curl -s "$BASE_URL/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

Fields:
- `status` (`string`): liveness state.

## GET /config

Returns effective non-secret runtime configuration.

Example:

```bash
curl -s "$BASE_URL/config"
```

Expected response shape:

```json
{
  "portainer_base_url": "http://portainer.local",
  "proxmox_stats_url": "http://proxmox-stats.local",
  "interval": 30
}
```

Fields:
- `portainer_base_url` (`string|null`)
- `proxmox_stats_url` (`string|null`)
- `interval` (`int`)

## GET /api/registry/raw

Returns `checks.yml` as parsed/validated.

Example:

```bash
curl -s "$BASE_URL/api/registry/raw"
```

Expected response shape:

```json
{
  "defaults": {
    "interval_s": 30,
    "timeout_s": 3,
    "retries": 1
  },
  "checks": [
    {
      "id": "open-webui",
      "type": "http",
      "url": "http://open-webui.local/health",
      "tags": ["core"],
      "interval_s": null,
      "timeout_s": null,
      "retries": null
    }
  ]
}
```

Fields:
- `defaults` (`object`)
- `checks` (`array` of check definitions)

## GET /api/registry

Returns normalized checks keyed by check ID, with defaults applied.

Example:

```bash
curl -s "$BASE_URL/api/registry"
```

Expected response shape:

```json
{
  "defaults": {
    "interval_s": 30,
    "timeout_s": 3,
    "retries": 1
  },
  "checks": {
    "open-webui": {
      "id": "open-webui",
      "type": "http",
      "url": "http://open-webui.local/health",
      "tags": ["core"],
      "interval_s": 30,
      "timeout_s": 3,
      "retries": 1
    }
  },
  "count": 1
}
```

Fields:
- `defaults` (`object`)
- `checks` (`object` keyed by check id)
- `count` (`int`)

## GET /api/status/checks

Returns latest known state for each check.

Example:

```bash
curl -s "$BASE_URL/api/status/checks"
```

Expected response shape:

```json
{
  "open-webui": {
    "id": "open-webui",
    "type": "http",
    "ok": true,
    "last_run": "2026-02-24T15:00:00+00:00",
    "last_ok": "2026-02-24T15:00:00+00:00",
    "last_change": "2026-02-24T14:00:00+00:00",
    "latency_ms": 42,
    "status_code": 200,
    "error": null
  }
}
```

Fields per check state:
- `id` (`string`)
- `type` (`string`)
- `ok` (`bool|null`)
- `last_run` (`string|null`)
- `last_ok` (`string|null`)
- `last_change` (`string|null`)
- `latency_ms` (`int|null`)
- `status_code` (`int|null`)
- `error` (`string|null`)

## GET /api/status/summary

Aggregate status counts from current check state.

Example:

```bash
curl -s "$BASE_URL/api/status/summary"
```

Expected response shape:

```json
{
  "total": 12,
  "up": 10,
  "down": 1,
  "unknown": 1,
  "down_checks": [
    {
      "id": "wiki",
      "type": "http",
      "ok": false,
      "last_run": "2026-02-24T15:00:00+00:00",
      "last_ok": "2026-02-24T14:50:00+00:00",
      "last_change": "2026-02-24T14:55:00+00:00",
      "latency_ms": 120,
      "status_code": 503,
      "error": "service unavailable"
    }
  ]
}
```

Fields:
- `total`, `up`, `down`, `unknown` (`int`)
- `down_checks` (`array` of check-state objects)

## GET /api/status/events

Recent transition events, newest first.

Example:

```bash
curl -s "$BASE_URL/api/status/events?limit=20"
```

Expected response shape:

```json
[
  {
    "ts": "2026-02-24T15:01:00+00:00",
    "id": "wiki",
    "event": "DOWN",
    "ok": false,
    "latency_ms": 120,
    "status_code": 503,
    "error": "service unavailable"
  },
  {
    "ts": "2026-02-24T15:02:00+00:00",
    "id": "wiki",
    "event": "UP",
    "ok": true,
    "latency_ms": 55,
    "status_code": 200,
    "error": null
  }
]
```

Query params:
- `limit` (`int`, default `50`, min `1`, max `500`)

Fields per event:
- `ts`, `id`, `event` (`string`)
- `ok` (`bool|null`)
- `latency_ms` (`int|null`)
- `status_code` (`int|null`)
- `error` (`string|null`)

## GET /api/ops/summary

Unified ops summary combining checks, cached proxmox status, docker placeholder, and recent events.

Example:

```bash
curl -s "$BASE_URL/api/ops/summary"
```

Expected response shape:

```json
{
  "timestamp": "2026-02-24T15:02:00Z",
  "overall": "warn",
  "services": {
    "up": 10,
    "down": 1,
    "down_list": ["wiki"]
  },
  "proxmox": {
    "status": "warn",
    "issues": [
      {
        "kind": "ct_disk_high",
        "vmid": 111,
        "name": "dashboards",
        "usage_percent": 91.65
      }
    ],
    "last_fetch_ts": "2026-02-24T15:01:45Z",
    "last_error": null
  },
  "docker": {
    "status": "unknown",
    "note": "portainer checks not enabled"
  },
  "recent_events": [
    {
      "ts": "2026-02-24T15:01:00+00:00",
      "id": "wiki",
      "event": "DOWN"
    },
    {
      "ts": "2026-02-24T15:01:30+00:00",
      "id": "wiki",
      "event": "UP"
    }
  ]
}
```

Fields:
- `timestamp` (`string`, UTC ISO-8601)
- `overall` (`ok|warn|crit`)
- `services.up` (`int`)
- `services.down` (`int`)
- `services.down_list` (`array[string]`)
- `proxmox.status` (`ok|warn|crit|unknown|unavailable`)
- `proxmox.issues` (`array[object]`)
- `proxmox.last_fetch_ts` (`string|null`)
- `proxmox.last_error` (`string|null`)
- `docker.status` (`unknown`)
- `docker.note` (`string`)
- `recent_events[]` objects with `ts`, `id`, `event`

Notes:
- This endpoint does not call `proxmox-stats` live; it reads cached state.
- On upstream issues, degraded proxmox fields are returned with HTTP `200`.

## GET /api/ops/health

Dependency reachability view for control-plane dependencies using cached state only.

Example:

```bash
curl -s "$BASE_URL/api/ops/health"
```

Expected response shape:

```json
{
  "timestamp": "2026-02-24T15:02:00Z",
  "dependencies": {
    "proxmox_stats": {
      "status": "ok",
      "last_fetch_ts": "2026-02-24T15:01:45Z",
      "last_error": null,
      "note": null
    },
    "ntfy": {
      "status": "unknown",
      "note": "ntfy checks not enabled"
    },
    "portainer": {
      "status": "unknown",
      "note": "portainer checks not enabled"
    }
  }
}
```

Fields:
- `timestamp` (`string`, UTC ISO-8601)
- `dependencies.proxmox_stats.status` (`ok|unknown|unavailable`)
- `dependencies.proxmox_stats.last_fetch_ts` (`string|null`)
- `dependencies.proxmox_stats.last_error` (`string|null`)
- `dependencies.proxmox_stats.note` (`string|null`)
- `dependencies.ntfy.status` (`unknown`)
- `dependencies.ntfy.note` (`string`)
- `dependencies.portainer.status` (`unknown`)
- `dependencies.portainer.note` (`string`)

Notes:
- `/health` remains process liveness and is separate from this endpoint.
- This endpoint does not make live network calls.

## POST /api/alerts/test

Sends a test ntfy notification for a specific check.

Example:

```bash
curl -s -X POST "$BASE_URL/api/alerts/test?check_id=open-webui"
```

Success response:

```json
{
  "ok": true,
  "check_id": "open-webui",
  "channel": "ntfy"
}
```

Fields:
- `ok` (`bool`)
- `check_id` (`string`)
- `channel` (`string`)

Error cases:
- HTTP `400` if `NTFY_URL`/`NTFY_TOPIC` are missing.
- HTTP `404` if `check_id` does not exist in normalized registry.
