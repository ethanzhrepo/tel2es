#!/usr/bin/env python3
"""
FastAPI REST Server for Telegram Scraper
Provides search and retrieval endpoints for scraped messages
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import TelegramConfig
from storage import ElasticsearchClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Telegram Scraper API",
    description="Search and retrieve Telegram messages stored in Elasticsearch",
    version="1.0.0"
)

# Global Elasticsearch client
es_client: Optional[ElasticsearchClient] = None
monitor_health_path = Path('config/monitor_health.json')


def _parse_epoch_ms(value: int) -> int:
    ts = int(value)
    if ts < 10**12:
        raise ValueError("begin must be epoch milliseconds")
    return ts



# Response models
class MessageResponse(BaseModel):
    """Single message response"""
    message_id: int
    chat_id: int
    chat_title: str
    chat_type: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_bot: bool = False
    timestamp: int = Field(..., description="Epoch milliseconds")
    text: str
    raw_text: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    forward_from_chat_id: Optional[int] = None
    entities: Optional[List[Dict[str, Any]]] = None
    media: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    score: Optional[float] = Field(None, description="Relevance score (for search results)")


class SearchResponse(BaseModel):
    """Search results response"""
    total: int = Field(..., description="Total number of matching messages")
    hits: List[MessageResponse] = Field(..., description="List of matching messages")
    query: Dict[str, Any] = Field(..., description="Query parameters used")


class LatestResponse(BaseModel):
    """Latest messages response"""
    total: int = Field(..., description="Total number of messages in time range")
    hits: List[MessageResponse] = Field(..., description="List of messages")
    query: Dict[str, Any] = Field(..., description="Query parameters used")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    elasticsearch: str
    index: str
    timestamp: datetime
    ingest: Optional[Dict[str, Any]] = None


@app.on_event("startup")
async def startup_event():
    """Initialize Elasticsearch client on startup"""
    global es_client

    try:
        config = TelegramConfig()
        es_config = config.get_elasticsearch_config()

        es_client = ElasticsearchClient(
            hosts=es_config.get('hosts', ['http://elasticsearch:9200']),
            index=es_config.get('index', 'telegram_messages'),
            username=es_config.get('username', ''),
            password=es_config.get('password', '')
        )

        # Ensure index exists
        await es_client.initialize_index()
        logger.info("Elasticsearch client initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize Elasticsearch client: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close Elasticsearch client on shutdown"""
    global es_client

    if es_client:
        await es_client.close()
        logger.info("Elasticsearch client closed")


@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint"""
    return {
        "service": "Telegram Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "search": "/search",
            "latest": "/latest"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    global es_client

    if not es_client:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")

    try:
        # Check Elasticsearch connectivity
        await es_client.client.info()
        es_status = "connected"
    except Exception as e:
        logger.error(f"Elasticsearch health check failed: {e}")
        es_status = "disconnected"

    ingest = None
    if monitor_health_path.exists():
        try:
            ingest = json.loads(monitor_health_path.read_text(encoding='utf-8'))
        except Exception as e:
            ingest = {"status": "unavailable", "error": str(e)}

    return HealthResponse(
        status="healthy" if es_status == "connected" else "unhealthy",
        elasticsearch=es_status,
        index=es_client.index,
        timestamp=datetime.now(),
        ingest=ingest
    )


@app.get("/search", response_model=SearchResponse)
async def search_messages(
    keywords: str = Query(..., description="Search keywords (full-text search on message text)"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format: 2024-01-01T00:00:00)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format: 2024-01-01T23:59:59)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Search messages by keywords and time range

    Returns messages sorted by relevance score (most relevant first)
    """
    global es_client

    if not es_client:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")

    try:
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        # Search messages
        result = await es_client.search_messages(
            keywords=keywords,
            start_time=start_dt,
            end_time=end_dt,
            limit=limit,
            offset=offset
        )

        # Convert to response model
        messages = []
        for hit in result['hits']:
            # Extract score if present
            score = hit.pop('_score', None)
            messages.append(MessageResponse(**hit, score=score))

        return SearchResponse(
            total=result['total'],
            hits=messages,
            query={
                "keywords": keywords,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
                "offset": offset
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {e}")
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/latest", response_model=LatestResponse)
async def get_latest_messages(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    begin: Optional[int] = Query(None, description="Begin timestamp (epoch milliseconds)"),
    size: Optional[int] = Query(None, ge=1, le=100, description="Alias for limit (1-100)")
):
    """
    Get latest messages sorted by timestamp

    Returns messages sorted by timestamp (newest first)
    """
    global es_client

    if not es_client:
        raise HTTPException(status_code=503, detail="Elasticsearch client not initialized")

    try:
        if size is not None:
            limit = size

        start_ms = None
        if begin is not None:
            start_ms = _parse_epoch_ms(begin)

        # Get latest messages
        result = await es_client.get_latest_messages(
            start_ms=start_ms,
            limit=limit,
            offset=offset
        )

        # Convert to response model
        messages = [MessageResponse(**hit) for hit in result['hits']]

        return LatestResponse(
            total=result['total'],
            hits=messages,
            query={
                "begin": begin,
                "limit": limit,
                "size": size,
                "offset": offset
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Get latest messages failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get latest messages: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Get API configuration
    config = TelegramConfig()
    api_config = config.get_api_config()

    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 8000)

    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
