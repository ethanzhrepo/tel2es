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
