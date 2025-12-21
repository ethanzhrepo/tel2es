"""
Elasticsearch Storage for Telegram Messages
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch client for storing and querying Telegram messages"""

    @staticmethod
    def _coerce_timestamp_ms(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                return value
        return value

    def __init__(self, hosts: List[str], index: str, username: str = '', password: str = ''):
        """
        Initialize Elasticsearch client

        Args:
            hosts: List of Elasticsearch hosts
            index: Index name for storing messages
            username: Optional username for authentication
            password: Optional password for authentication
        """
        self.index = index

        # Setup authentication if provided
        if username and password:
            self.client = AsyncElasticsearch(
                hosts,
                basic_auth=(username, password)
            )
        else:
            self.client = AsyncElasticsearch(hosts)

        logger.info(f"Initialized Elasticsearch client for index: {index}")

    async def initialize_index(self):
        """Create index with proper mappings if it doesn't exist"""
        # Check if index exists (ES 9.x compatible)
        try:
            index_exists = await self.client.indices.exists(index=self.index)
        except Exception as e:
            logger.warning(f"Error checking index existence: {e}")
            index_exists = False

        if not index_exists:
            # Define index settings and mappings
            await self.client.indices.create(
                index=self.index,
                mappings={
                    "properties": {
                        "message_id": {"type": "long"},
                        "chat_id": {"type": "long"},
                        "chat_title": {"type": "keyword"},
                        "chat_type": {"type": "keyword"},
                        "user_id": {"type": "long"},
                        "username": {"type": "keyword"},
                        "first_name": {"type": "text"},
                        "is_bot": {"type": "boolean"},
                        "timestamp": {"type": "date"},
                        "text": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "raw_text": {"type": "text"},
                        "reply_to_message_id": {"type": "long"},
                        "forward_from_chat_id": {"type": "long"},
                        "entities": {"type": "object", "enabled": False},
                        "media": {"type": "object", "enabled": False},
                        "extracted_data": {
                            "properties": {
                                "addresses": {
                                    "properties": {
                                        "ethereum": {"type": "keyword"},
                                        "solana": {"type": "keyword"},
                                        "bitcoin": {"type": "keyword"}
                                    }
                                },
                                "symbols": {"type": "keyword"},
                                "crypto_currencies": {"type": "object", "enabled": False},
                                "urls": {"type": "object", "enabled": False},
                                "prices": {"type": "object", "enabled": False},
                                "keywords": {"type": "keyword"},
                                "sentiment": {"type": "keyword"},
                                "raw_text": {"type": "text"}
                            }
                        }
                    }
                }
            )
            logger.info(f"Created index: {self.index}")
        else:
            logger.info(f"Index already exists: {self.index}")

    async def index_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Index a single message

        Args:
            message_data: Message data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use message_id and chat_id as document ID for deduplication
            doc_id = f"{message_data['chat_id']}_{message_data['message_id']}"

            await self.client.index(
                index=self.index,
                id=doc_id,
                document=message_data
            )
            logger.debug(f"Indexed message: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to index message: {e}")
            return False

    async def bulk_index_messages(self, messages: List[Dict[str, Any]]) -> tuple:
        """
        Bulk index multiple messages

        Args:
            messages: List of message data dictionaries

        Returns:
            Tuple of (success_count, failed_count)
        """
        if not messages:
            return (0, 0)

        actions = []
        for msg in messages:
            doc_id = f"{msg['chat_id']}_{msg['message_id']}"
            actions.append({
                "_index": self.index,
                "_id": doc_id,
                "_source": msg
            })

        try:
            success, failed = await async_bulk(self.client, actions, raise_on_error=False)
            logger.info(f"Bulk indexed {success} messages, {len(failed)} failed")
            return (success, len(failed))
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return (0, len(messages))

    async def search_messages(
        self,
        keywords: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search messages by keywords and time range

        Args:
            keywords: Search keywords (full-text search on text field)
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Dictionary with 'total', 'hits' keys
        """
        query = {"bool": {"must": []}}

        # Add keyword search
        if keywords:
            query["bool"]["must"].append({
                "multi_match": {
                    "query": keywords,
                    "fields": ["text^2", "raw_text", "extracted_data.keywords"],
                    "type": "best_fields"
                }
            })

        # Add time range filter
        if start_time or end_time:
            time_range = {}
            if start_time:
                time_range["gte"] = start_time.isoformat()
            if end_time:
                time_range["lte"] = end_time.isoformat()

            query["bool"]["must"].append({
                "range": {
                    "timestamp": time_range
                }
            })

        # If no conditions, match all
        if not query["bool"]["must"]:
            query = {"match_all": {}}

        try:
            response = await self.client.search(
                index=self.index,
                query=query,
                size=limit,
                from_=offset,
                sort=[{"_score": "desc"}, {"timestamp": "desc"}]
            )

            hits = []
            for hit in response['hits']['hits']:
                doc = hit['_source']
                doc['timestamp'] = self._coerce_timestamp_ms(doc.get('timestamp'))
                doc['_score'] = hit['_score']
                hits.append(doc)

            return {
                'total': response['hits']['total']['value'],
                'hits': hits
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {'total': 0, 'hits': []}

    async def get_latest_messages(
        self,
        start_ms: Optional[int] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get latest messages sorted by timestamp

        Args:
            start_ms: Start of time range (epoch milliseconds)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Dictionary with 'total', 'hits' keys
        """
        query = {"bool": {"must": []}}

        # Add time range filter
        if start_ms is not None:
            time_range = {}
            if start_ms is not None:
                time_range["gte"] = start_ms

            query["bool"]["must"].append({
                "range": {
                    "timestamp": time_range
                }
            })

        # If no time range, match all
        if not query["bool"]["must"]:
            query = {"match_all": {}}

        try:
            response = await self.client.search(
                index=self.index,
                query=query,
                size=limit,
                from_=offset,
                sort=[{"timestamp": "desc"}]
            )

            hits = []
            for hit in response['hits']['hits']:
                doc = hit['_source']
                doc['timestamp'] = self._coerce_timestamp_ms(doc.get('timestamp'))
                hits.append(doc)

            return {
                'total': response['hits']['total']['value'],
                'hits': hits
            }
        except Exception as e:
            logger.error(f"Get latest messages failed: {e}")
            return {'total': 0, 'hits': []}

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """
        Delete a message from the index

        Args:
            chat_id: Chat ID
            message_id: Message ID

        Returns:
            True if successful, False otherwise
        """
        try:
            doc_id = f"{chat_id}_{message_id}"
            await self.client.delete(index=self.index, id=doc_id)
            logger.info(f"Deleted message: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    async def close(self):
        """Close the Elasticsearch client"""
        await self.client.close()
        logger.info("Closed Elasticsearch client")
