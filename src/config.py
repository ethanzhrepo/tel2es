"""
Telegram Scraper Configuration Management
"""

import os
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class TelegramConfig:
    """Telegram configuration manager"""

    def __init__(self, config_file: str = None):
        # Support environment variable for config file path
        if config_file is None:
            config_file = os.getenv('CONFIG_FILE', 'config.yml')
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(self.config_file)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}

        # Default configuration
        return {
            'telegram': {
                'api_id': '',
                'api_hash': '',
                'phone': '',
                'session': 'tel2es'
            },
            'monitoring': {
                'groups': [],
                'channels': []
            },
            'elasticsearch': {
                'hosts': ['http://elasticsearch:9200'],
                'index': 'telegram_messages',
                'username': '',
                'password': ''
            },
            'api': {
                'host': '0.0.0.0',
                'port': 8000
            },
            'advanced': {
                'filters': {
                    'min_message_length': 0,
                    'ignore_bots': False,
                    'keywords': []
                },
                'extraction': {
                    'extract_urls': True,
                    'extract_addresses': True,
                    'extract_symbols': True,
                    'sentiment_analysis': True
                },
                'monitoring': {
                    'stall_seconds': 1800,
                    'watchdog_interval_seconds': 60,
                    'poll_interval_seconds': 300,
                    'poll_batch_limit': 200,
                    'min_resync_interval_seconds': 300,
                    'health_write_interval_seconds': 60
                }
            }
        }

    def save_config(self):
        """Save configuration to YAML file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"Configuration saved to {self.config_file}")

    def get_telegram_config(self) -> Dict[str, str]:
        """Get Telegram configuration"""
        return self.config.get('telegram', {})

    def get_monitoring_config(self) -> Dict[str, List]:
        """Get monitoring configuration"""
        return self.config.get('monitoring', {'groups': [], 'channels': []})

    def get_elasticsearch_config(self) -> Dict[str, Any]:
        """Get Elasticsearch configuration"""
        return self.config.get('elasticsearch', {})

    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self.config.get('api', {})

    def get_advanced_config(self) -> Dict[str, Any]:
        """Get advanced configuration"""
        return self.config.get('advanced', {})

    def update_monitoring_config(self, selected_chats: List[Dict[str, Any]]):
        """Update monitoring configuration with selected chats"""
        groups = []
        channels = []

        for chat in selected_chats:
            chat_info = {
                'id': chat['id'],
                'title': chat['title'],
                'type': chat['type']
            }
            if chat['type'] in ['group', 'supergroup']:
                groups.append(chat_info)
            elif chat['type'] == 'channel':
                channels.append(chat_info)

        self.config['monitoring'] = {
            'groups': groups,
            'channels': channels
        }
        logger.info(f"Updated monitoring config: {len(groups)} groups, {len(channels)} channels")

    def get_monitored_chat_ids(self) -> List[int]:
        """Get list of all monitored chat IDs"""
        monitoring = self.get_monitoring_config()
        chat_ids = []

        for group in monitoring.get('groups', []):
            chat_ids.append(group['id'])
        for channel in monitoring.get('channels', []):
            chat_ids.append(channel['id'])

        return chat_ids

    def get_monitored_chats(self) -> List[Dict[str, Any]]:
        """Get list of all monitored chats with metadata"""
        monitoring = self.get_monitoring_config()
        chats = []

        chats.extend(monitoring.get('groups', []))
        chats.extend(monitoring.get('channels', []))

        return chats
