#!/usr/bin/env python3
"""
Telegram Message Scraper
Monitors Telegram channels/groups and stores messages in Elasticsearch
"""

import asyncio
import json
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, VSplit
from prompt_toolkit.widgets import CheckboxList, Frame, Button

from config import TelegramConfig
from extractor import MessageExtractor
from storage import ElasticsearchClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress Telethon debug logs
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.WARNING)


class TelegramConfigUI:
    """Telegram configuration interactive UI"""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.chats = []
        self.selected_chats = []
        self.checkbox_list = None
        self.app = None
        self.confirm_exit = False

    async def get_chats(self) -> List[Dict[str, Any]]:
        """Get all groups and channels"""
        chats = []

        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity

            if isinstance(entity, (Channel, Chat)):
                # Determine chat type
                if isinstance(entity, Channel):
                    if entity.broadcast:
                        chat_type = 'channel'
                    else:
                        chat_type = 'supergroup'
                else:  # isinstance(entity, Chat)
                    chat_type = 'group'

                chats.append({
                    'id': entity.id,
                    'title': dialog.title,
                    'type': chat_type,
                    'username': getattr(entity, 'username', None)
                })

        return sorted(chats, key=lambda x: x['title'])

    def create_ui(self) -> Application:
        """Create user interface"""
        # Get existing configuration
        config = TelegramConfig()
        existing_config = config.get_monitoring_config()
        existing_chat_ids = set()

        # Collect existing configured chat IDs
        for group in existing_config.get('groups', []):
            existing_chat_ids.add(group['id'])
        for channel in existing_config.get('channels', []):
            existing_chat_ids.add(channel['id'])

        # Create checkbox list, pre-select existing items
        checkbox_values = []
        default_values = []

        for chat in self.chats:
            checkbox_values.append((chat, f"{chat['title']} ({chat['type']})"))
            # If this chat is already in config, select it by default
            if chat['id'] in existing_chat_ids:
                default_values.append(chat)

        self.checkbox_list = CheckboxList(values=checkbox_values, default_values=default_values)

        # Create buttons with shortcuts
        save_button = Button(text='Save Config (F8)', handler=self._save_config)
        cancel_button = Button(text='Cancel (ESC)', handler=self._cancel)

        # Create dynamic title
        def get_title():
            if self.confirm_exit:
                return 'Confirm exit? Press ESC again to exit, any other key to cancel'
            selected_count = len(self.checkbox_list.current_values)
            return f'Select channels/groups to monitor (Selected: {selected_count}) (Space:Select Tab:Switch F8:Save ESC:Exit)'

        # Create layout
        checkbox_frame = Frame(
            body=self.checkbox_list,
            title=get_title,
            height=min(len(self.chats) + 3, 20)
        )

        buttons_container = VSplit([
            save_button,
            cancel_button
        ], padding=1)

        root_container = HSplit([
            checkbox_frame,
            buttons_container
        ])

        layout = Layout(root_container, focused_element=self.checkbox_list)

        # Create key bindings
        kb = KeyBindings()

        @kb.add('tab')
        def _(event):
            """Tab: Switch focus"""
            event.app.layout.focus_next()

        @kb.add('s-tab')  # Shift+Tab
        def _(event):
            """Shift+Tab: Reverse switch focus"""
            event.app.layout.focus_previous()

        @kb.add('escape')
        def _(event):
            """ESC: Ask to exit"""
            if not self.confirm_exit:
                # First ESC, show confirmation
                self.confirm_exit = True
                event.app.invalidate()
            else:
                # Second ESC, confirm exit
                print("\nExiting configuration (not saved)")
                event.app.exit(result='cancel')

        @kb.add('space')
        def _(event):
            """Space: Toggle selection"""
            event.app.layout.current_control.toggle_current()
            event.app.invalidate()

        @kb.add('<any>')
        def _(event):
            """Any key: Cancel exit confirmation"""
            if self.confirm_exit and event.key_sequence[0].key not in ['escape', 'f8', 'tab', 's-tab', 'space']:
                self.confirm_exit = False
                event.app.invalidate()

        @kb.add('f8')
        def _(event):
            """F8: Save and exit"""
            self._save_config()

        @kb.add('c-c')
        @kb.add('c-d')
        def _(event):
            """Ctrl+C/Ctrl+D: Force exit"""
            event.app.exit()

        return Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True
        )

    def _save_config(self):
        """Save configuration"""
        self.selected_chats = [chat for chat in self.checkbox_list.current_values]
        group_count = len([chat for chat in self.selected_chats if chat['type'] in ['group', 'supergroup']])
        channel_count = len([chat for chat in self.selected_chats if chat['type'] == 'channel'])
        print(f"\nSelected {len(self.selected_chats)} chats:")
        print(f"  - Groups: {group_count}")
        print(f"  - Channels: {channel_count}")
        self.app.exit(result='save')

    def _cancel(self):
        """Cancel configuration"""
        print("\nExiting configuration (not saved)")
        self.app.exit(result='cancel')

    async def run_config(self) -> Optional[List[Dict[str, Any]]]:
        """Run configuration interface"""
        print("Fetching groups and channels list...")
        self.chats = await self.get_chats()

        if not self.chats:
            print("No groups or channels found")
            return None

        self.app = self.create_ui()
        result = await self.app.run_async()

        if result == 'save':
            return self.selected_chats
        return None


class TelegramMonitor:
    """Telegram message monitor"""

    def __init__(self, config: TelegramConfig, es_client: Optional[ElasticsearchClient] = None):
        self.config = config
        self.client = None
        self.extractor = MessageExtractor()
        self.es_client = es_client
        self.running = False

    async def initialize(self):
        """Initialize Telegram client"""
        telegram_config = self.config.get_telegram_config()

        if not all([telegram_config.get('api_id'), telegram_config.get('api_hash')]):
            raise ValueError("Please configure Telegram API info in config.yml")

        # Store session in config/sessions directory for persistence
        session_name = telegram_config.get('session', 'tel2es')
        session_path = f'config/sessions/{session_name}'
        self.client = TelegramClient(
            session_path,
            int(telegram_config['api_id']),
            telegram_config['api_hash']
        )

        # Suppress logs during connection
        old_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)

        try:
            await self.client.start(phone=telegram_config.get('phone'))
        finally:
            logging.getLogger().setLevel(old_level)

        # Initialize Elasticsearch client if not provided
        if self.es_client is None:
            es_config = self.config.get_elasticsearch_config()
            self.es_client = ElasticsearchClient(
                hosts=es_config.get('hosts', ['http://elasticsearch:9200']),
                index=es_config.get('index', 'telegram_messages'),
                username=es_config.get('username', ''),
                password=es_config.get('password', '')
            )
            await self.es_client.initialize_index()
            logger.info("Elasticsearch client initialized")

    async def start_monitoring(self):
        """Start monitoring"""
        monitoring_config = self.config.get_monitoring_config()
        all_chats = monitoring_config.get('groups', []) + monitoring_config.get('channels', [])

        if not all_chats:
            logger.error("No groups or channels configured for monitoring")
            return

        logger.info(f"Starting monitoring of {len(all_chats)} groups/channels")
        logger.info("Monitored chats:")
        for chat in all_chats:
            logger.info(f"  - {chat['title']} (ID: {chat['id']}, Type: {chat['type']})")

        # Register event handlers
        @self.client.on(events.NewMessage)
        async def handle_new_message(event):
            logger.debug(f"New message event from chat ID: {event.chat_id}")
            await self._handle_message(event, 'new')

        @self.client.on(events.MessageEdited)
        async def handle_edited_message(event):
            logger.debug(f"Edited message event from chat ID: {event.chat_id}")
            # Optionally handle edits
            # await self._handle_message(event, 'edit')

        @self.client.on(events.MessageDeleted)
        async def handle_deleted_message(event):
            logger.debug(f"Deleted message event from chat ID: {event.chat_id}")
            await self._handle_delete(event)

        self.running = True
        logger.info("Monitoring started, press Ctrl+C to stop")
        logger.info("Waiting for messages...")

        try:
            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Stop signal received")
        finally:
            self.running = False
            if self.es_client:
                await self.es_client.close()

    async def _handle_message(self, event, message_type: str):
        """Handle message event"""
        try:
            # Check if this is a monitored chat
            chat_id = event.chat_id
            monitoring_config = self.config.get_monitoring_config()
            all_chats = monitoring_config.get('groups', []) + monitoring_config.get('channels', [])

            logger.debug(f"Processing message: Chat ID {chat_id}, Type {message_type}")

            # Fix ID matching: handle Telegram's ID format differences
            def normalize_chat_id(id_value):
                """Normalize chat ID, handle -100 prefix"""
                if isinstance(id_value, str):
                    id_value = int(id_value)

                # If negative and starts with -100, extract actual ID
                if id_value < 0 and str(abs(id_value)).startswith('100'):
                    return abs(id_value) - 1000000000000  # Remove -100 prefix
                return abs(id_value)  # Use positive for comparison

            normalized_event_id = normalize_chat_id(chat_id)

            monitored_chat = None
            for chat in all_chats:
                config_id = normalize_chat_id(chat['id'])
                if config_id == normalized_event_id:
                    monitored_chat = chat
                    break

            if not monitored_chat:
                logger.debug(f"Chat ID {chat_id} (normalized: {normalized_event_id}) not in monitoring list, skipping")
                logger.debug(f"Monitored IDs: {[normalize_chat_id(chat['id']) for chat in all_chats]}")
                return

            logger.info(f"Processing message from '{monitored_chat['title']}'")

            # Get message information
            message = event.message
            sender = await message.get_sender()

            # Extract structured data
            text = message.message or ''
            extracted_data = await self.extractor.extract_data(text)

            logger.debug(f"Message text: {text[:100]}...")

            # Build message data
            message_data = {
                'message_id': message.id,
                'chat_id': chat_id,
                'chat_title': monitored_chat['title'],
                'chat_type': monitored_chat['type'],
                'user_id': sender.id if sender else None,
                'username': getattr(sender, 'username', None),
                'first_name': getattr(sender, 'first_name', None),
                'is_bot': getattr(sender, 'bot', False),
                'timestamp': datetime.fromtimestamp(message.date.timestamp()),
                'text': text,
                'raw_text': extracted_data.get('raw_text', text),
                'reply_to_message_id': message.reply_to_msg_id,
                'forward_from_chat_id': getattr(message.forward, 'chat_id', None) if message.forward else None,
                'entities': self._extract_entities(message),
                'media': self._extract_media(message),
                'extracted_data': extracted_data
            }

            # Index to Elasticsearch
            await self._store_message(message_data)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def _handle_delete(self, event):
        """Handle delete event"""
        try:
            # Check if this is a monitored chat
            chat_id = event.chat_id
            monitoring_config = self.config.get_monitoring_config()
            all_chats = monitoring_config.get('groups', []) + monitoring_config.get('channels', [])

            # Use same ID normalization logic
            def normalize_chat_id(id_value):
                """Normalize chat ID, handle -100 prefix"""
                if isinstance(id_value, str):
                    id_value = int(id_value)

                if id_value < 0 and str(abs(id_value)).startswith('100'):
                    return abs(id_value) - 1000000000000
                return abs(id_value)

            normalized_event_id = normalize_chat_id(chat_id)

            monitored_chat = None
            for chat in all_chats:
                config_id = normalize_chat_id(chat['id'])
                if config_id == normalized_event_id:
                    monitored_chat = chat
                    break

            if not monitored_chat:
                logger.debug(f"Delete event: Chat ID {chat_id} not in monitoring list, skipping")
                return

            # Delete messages from Elasticsearch
            for message_id in event.deleted_ids:
                await self.es_client.delete_message(chat_id, message_id)
                logger.info(f"Deleted message {message_id} from '{monitored_chat['title']}'")

        except Exception as e:
            logger.error(f"Error processing delete event: {e}")

    def _extract_entities(self, message) -> List[Dict[str, Any]]:
        """Extract message entities"""
        entities = []
        if hasattr(message, 'entities') and message.entities:
            for entity in message.entities:
                entity_data = {
                    'type': entity.__class__.__name__.lower(),
                    'offset': entity.offset,
                    'length': entity.length
                }

                # Add type-specific info
                if hasattr(entity, 'url'):
                    entity_data['url'] = entity.url
                elif hasattr(entity, 'user_id'):
                    entity_data['user_id'] = entity.user_id

                entities.append(entity_data)

        return entities

    def _extract_media(self, message) -> Optional[Dict[str, Any]]:
        """Extract media information"""
        if not message.media:
            return None

        media_data = {
            'type': message.media.__class__.__name__.lower()
        }

        # Add type-specific info
        if hasattr(message.media, 'photo'):
            media_data.update({
                'file_id': str(message.media.photo.id),
                'caption': getattr(message, 'message', '')
            })
        elif hasattr(message.media, 'document'):
            doc = message.media.document
            media_data.update({
                'file_id': str(doc.id),
                'file_size': doc.size,
                'mime_type': doc.mime_type,
                'caption': getattr(message, 'message', '')
            })

        return media_data

    async def _store_message(self, message_data: Dict[str, Any]):
        """Store message to Elasticsearch"""
        if self.es_client:
            success = await self.es_client.index_message(message_data)
            if success:
                logger.info(f"Indexed message {message_data['message_id']} from {message_data['chat_title']}")
            else:
                logger.error(f"Failed to index message {message_data['message_id']}")

        # Also print to console for debugging
        message_json = json.dumps(message_data, ensure_ascii=False, separators=(',', ':'), default=str)
        print(f"[{datetime.now().isoformat()}] {message_json}")


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py config  - Configure monitored groups/channels")
        print("  python main.py login   - Login to Telegram")
        print("  python main.py start   - Start monitoring")
        return

    command = sys.argv[1]
    config = TelegramConfig()

    if command == 'login':
        # Login mode
        telegram_config = config.get_telegram_config()

        if not all([telegram_config.get('api_id'), telegram_config.get('api_hash')]):
            print("Please configure Telegram API info in config.yml first:")
            print("telegram:")
            print("  api_id: 'your_api_id'")
            print("  api_hash: 'your_api_hash'")
            print("  phone: 'your_phone_number'")
            return

        # Initialize client with session in config/sessions directory
        session_name = telegram_config.get('session', 'tel2es')
        session_path = f'config/sessions/{session_name}'
        client = TelegramClient(
            session_path,
            int(telegram_config['api_id']),
            telegram_config['api_hash']
        )

        print("Connecting to Telegram...")
        await client.start(phone=telegram_config.get('phone'))
        print(f"Login successful! Session saved to {session_path}.session")
        await client.disconnect()

    elif command == 'config':
        # Configuration mode
        telegram_config = config.get_telegram_config()

        if not all([telegram_config.get('api_id'), telegram_config.get('api_hash')]):
            print("Please configure Telegram API info in config.yml first:")
            print("telegram:")
            print("  api_id: 'your_api_id'")
            print("  api_hash: 'your_api_hash'")
            print("  phone: 'your_phone_number'")
            return

        # Initialize client with session in config/sessions directory
        session_name = telegram_config.get('session', 'tel2es')
        session_path = f'config/sessions/{session_name}'
        client = TelegramClient(
            session_path,
            int(telegram_config['api_id']),
            telegram_config['api_hash']
        )

        # Suppress logs during connection
        old_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)

        try:
            await client.start(phone=telegram_config.get('phone'))
        finally:
            logging.getLogger().setLevel(old_level)

        # Run configuration UI
        ui = TelegramConfigUI(client)
        selected_chats = await ui.run_config()

        if selected_chats:
            config.update_monitoring_config(selected_chats)
            config.save_config()
            print(f"Saved configuration for {len(selected_chats)} groups/channels")
        else:
            print("Configuration cancelled")

        await client.disconnect()

    elif command == 'start':
        # Monitoring mode
        monitor = TelegramMonitor(config)

        # Validate configuration
        monitoring_config = config.get_monitoring_config()
        all_chats = monitoring_config.get('groups', []) + monitoring_config.get('channels', [])

        logger.info(f"Read {len(all_chats)} monitoring targets from configuration")

        if not all_chats:
            logger.error("No monitoring targets configured. Run 'python main.py config' first")
            return

        await monitor.initialize()
        await monitor.start_monitoring()

    else:
        print(f"Unknown command: {command}")
        print("Available commands: login, config, start")


if __name__ == '__main__':
    asyncio.run(main())
