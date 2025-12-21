# tel2es

A Docker-based Telegram message scraper that monitors channels and groups, extracts crypto-related data, and stores messages in Elasticsearch with a REST API for searching and retrieval.

## Features

- Monitor multiple Telegram channels and groups
- Extract crypto addresses (Ethereum, Solana, Bitcoin)
- Match crypto symbols via CoinGecko API
- Sentiment analysis (positive/negative/neutral)
- Store messages in Elasticsearch
- REST API for searching and retrieving messages
- Interactive CLI for channel selection
- Docker-based deployment

## Architecture

```
┌─────────────────┐
│   Telegram      │
│   Channels      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│   Scraper       │─────▶│  Elasticsearch   │
│   Container     │      │                  │
└─────────────────┘      └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │   API Server     │
                         │   (FastAPI)      │
                         └──────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Telegram API credentials (get from https://my.telegram.org/apps)
- Telegram account

## Quick Start

For deployment and usage instructions, please refer to [docker/README.md](docker/README.md).

## API Usage

The REST API runs on `http://localhost:8000`

### Health Check

```bash
curl http://localhost:8000/health
```

The response includes an optional `ingest` field that reflects the scraper runtime health
from `config/monitor_health.json` when the scraper is running.

Example:

```json
{
  "status": "healthy",
  "elasticsearch": "connected",
  "index": "telegram_messages",
  "timestamp": "2025-01-01T12:00:00.000000",
  "ingest": {
    "status": "running",
    "connected": true,
    "monitored_chats": 3,
    "last_event_at": "2025-01-01T12:00:10.000000",
    "last_event_age_seconds": 5.2,
    "last_resync_at": "2025-01-01T11:55:00.000000",
    "last_resync_status": "success",
    "last_resync_reason": "persistent timestamp outdated",
    "last_poll_at": "2025-01-01T12:00:00.000000",
    "updated_at": "2025-01-01T12:00:10.000000"
  }
}
```

### Search Messages

```bash
# Search by keywords
curl "http://localhost:8000/search?keywords=bitcoin&limit=10"

# Search with time range
curl "http://localhost:8000/search?keywords=pump&start_time=2024-01-01T00:00:00&end_time=2024-01-31T23:59:59&limit=20"
```

### Get Latest Messages

```bash
# Get latest 10 messages
curl "http://localhost:8000/latest?limit=10"

# Get latest messages in time range
curl "http://localhost:8000/latest?start_time=2024-01-01T00:00:00&end_time=2024-01-31T23:59:59&limit=50"
```

## Monitoring Recovery Settings

The scraper uses a watchdog + poll fallback to recover from stalled Telegram updates.
Adjust these in `config.yml` under `advanced.monitoring`:

```yaml
advanced:
  monitoring:
    stall_seconds: 1800                 # Trigger resync after no messages for N seconds
    watchdog_interval_seconds: 60       # Health check interval
    poll_interval_seconds: 300          # Fallback poll interval
    poll_batch_limit: 200               # Max messages per poll batch
    min_resync_interval_seconds: 300    # Minimum seconds between resync attempts
    health_write_interval_seconds: 60   # Health snapshot write interval
```
