.PHONY: help start stop restart login config test logs health clean check-config backup restore list-backups query

# Project paths
PROJECT_ROOT := ../
COMPOSE_FILE := docker-compose-with-es.yml
CONFIG_DIR := ./config
CONFIG_FILE := $(CONFIG_DIR)/config.yml
CONFIG_EXAMPLE := $(CONFIG_DIR)/config.yml.example
BACKUP_DIR := ./backups
ES_HOST := http://localhost:9200
ES_INDEX := telegram_messages

help:
	@echo "Telegram Scraper - Test Environment Commands"
	@echo "=============================================="
	@echo "make start       - Start all services (Elasticsearch, Scraper, API)"
	@echo "make stop        - Stop all services"
	@echo "make restart     - Restart all services"
	@echo "make login       - Login to Telegram (first time setup)"
	@echo "make config      - Configure monitored channels/groups"
	@echo "make test        - Run tests"
	@echo "make logs         - View scraper logs"
	@echo "make health       - Check service health"
	@echo "make clean        - Stop services and remove volumes"
	@echo "make check-config - Check and setup configuration"
	@echo ""
	@echo "=== Data Management ==="
	@echo "make backup       - Backup Elasticsearch data"
	@echo "make restore      - Restore Elasticsearch data from backup"
	@echo "make list-backups - List all available backups"
	@echo "make query KEYWORD=<word> N=<num> - Search messages by keyword (default N=10)"

check-config:
	@echo "Checking configuration..."
	@# Create config and data directories if they don't exist
	@mkdir -p "$(CONFIG_DIR)/sessions"
	@mkdir -p ./data
	@# Set proper permissions for Elasticsearch data directory (uid:gid 1000:0)
	@if [ -d ./data ] && [ -z "$$(ls -A ./data)" ]; then \
		chmod 775 ./data; \
		echo "Created data directory with proper permissions"; \
	fi
	@# Remove config.yml if it's a directory
	@if [ -d "$(CONFIG_FILE)" ]; then \
		echo "Removing incorrectly created config.yml directory..."; \
		rm -rf "$(CONFIG_FILE)"; \
	fi
	@# Copy from example if config doesn't exist
	@if [ ! -f "$(CONFIG_FILE)" ]; then \
		if [ ! -f "$(CONFIG_EXAMPLE)" ]; then \
			echo "Copying config example from project root..."; \
			cp "$(PROJECT_ROOT)/config.yml.example" "$(CONFIG_EXAMPLE)"; \
		fi; \
		echo "Creating $(CONFIG_FILE) from $(CONFIG_EXAMPLE)..."; \
		cp "$(CONFIG_EXAMPLE)" "$(CONFIG_FILE)"; \
	fi
	@# Check and prompt for missing credentials
	@api_id=$$(grep "api_id:" "$(CONFIG_FILE)" | sed "s/.*api_id: *['\"]*\([^'\"]*\)['\"]*$$/\1/" | tr -d ' '); \
	api_hash=$$(grep "api_hash:" "$(CONFIG_FILE)" | sed "s/.*api_hash: *['\"]*\([^'\"]*\)['\"]*$$/\1/" | tr -d ' '); \
	phone=$$(grep -E "^[[:space:]]*phone:" "$(CONFIG_FILE)" | sed "s/.*phone:[[:space:]]*['\"]\([^'\"#]*\).*/\1/" | tr -d ' '); \
	needs_update=0; \
	if [ -z "$$api_id" ] || [ "$$api_id" = "YOUR_API_ID" ]; then \
		echo ""; \
		read -p "Enter your Telegram API ID (from https://my.telegram.org/apps): " api_id; \
		sed -i.bak "s/api_id:.*/api_id: '$$api_id'/" "$(CONFIG_FILE)"; \
		needs_update=1; \
	fi; \
	if [ -z "$$api_hash" ] || [ "$$api_hash" = "YOUR_API_HASH" ]; then \
		read -p "Enter your Telegram API Hash: " api_hash; \
		sed -i.bak "s/api_hash:.*/api_hash: '$$api_hash'/" "$(CONFIG_FILE)"; \
		needs_update=1; \
	fi; \
	if [ -z "$$phone" ] || [ "$$phone" = "YOUR_PHONE_NUMBER" ]; then \
		read -p "Enter your phone number (international format, e.g., +1234567890): " phone; \
		sed -i.bak "s/phone:.*/phone: '$$phone'/" "$(CONFIG_FILE)"; \
		needs_update=1; \
	fi; \
	if [ $$needs_update -eq 1 ]; then \
		rm -f "$(CONFIG_FILE).bak"; \
		echo ""; \
		echo "✓ Configuration updated successfully!"; \
	else \
		echo "✓ Configuration is complete!"; \
	fi

start: check-config
	@echo "Starting Telegram Scraper services..."
	docker-compose -f $(COMPOSE_FILE) up -d
	@echo "Services started. Use 'make logs' to view output."
	@echo "API available at http://localhost:8000"

stop:
	@echo "Stopping Telegram Scraper services..."
	docker-compose -f $(COMPOSE_FILE) down
	@echo "Services stopped."

restart:
	@echo "Restarting Telegram Scraper services..."
	docker-compose -f $(COMPOSE_FILE) restart
	@echo "Services restarted."

login: check-config
	@echo "Login to Telegram..."
	@echo "You will be prompted for verification code."
	docker-compose -f $(COMPOSE_FILE) run --rm scraper python src/main.py login

config: check-config
	@echo "Configure monitored channels..."
	@echo "Use Space to select, Tab to navigate, F8 to save, ESC to exit."
	docker-compose -f $(COMPOSE_FILE) run --rm scraper python src/main.py config

test:
	@echo "Running tests..."
	docker-compose -f $(COMPOSE_FILE) run --rm scraper pytest tests/ -v

logs:
	@echo "Viewing scraper logs (Ctrl+C to exit)..."
	docker-compose -f $(COMPOSE_FILE) logs -f scraper

logs-api:
	@echo "Viewing API logs (Ctrl+C to exit)..."
	docker-compose -f $(COMPOSE_FILE) logs -f api

logs-all:
	@echo "Viewing all logs (Ctrl+C to exit)..."
	docker-compose -f $(COMPOSE_FILE) logs -f

health:
	@echo "Checking service health..."
	@echo ""
	@echo "=== Elasticsearch ==="
	@curl -s http://localhost:9200/_cluster/health?pretty || echo "Elasticsearch not responding"
	@echo ""
	@echo "=== API Server ==="
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not responding"
	@echo ""
	@echo "=== Docker Services ==="
	@docker-compose -f $(COMPOSE_FILE) ps

clean:
	@echo "Stopping services and removing data..."
	@echo "WARNING: This will delete all stored messages and Elasticsearch data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose -f $(COMPOSE_FILE) down; \
		if [ -d ./data ]; then \
			echo "Removing Elasticsearch data directory..."; \
			rm -rf ./data; \
		fi; \
		echo "Services stopped and data removed."; \
	else \
		echo "Cancelled."; \
	fi

build:
	@echo "Building Docker images..."
	docker-compose -f $(COMPOSE_FILE) build

rebuild:
	@echo "Rebuilding Docker images..."
	docker-compose -f $(COMPOSE_FILE) build --no-cache

status:
	@echo "Service status:"
	docker-compose -f $(COMPOSE_FILE) ps

shell:
	@echo "Opening shell in scraper container..."
	docker-compose -f $(COMPOSE_FILE) exec scraper /bin/bash

shell-api:
	@echo "Opening shell in API container..."
	docker-compose -f $(COMPOSE_FILE) exec api /bin/bash

backup:
	@echo "Backing up Elasticsearch data..."
	@mkdir -p "$(BACKUP_DIR)"
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	BACKUP_FILE="$(BACKUP_DIR)/telegram_messages_$$TIMESTAMP.json"; \
	echo "Creating backup: $$BACKUP_FILE"; \
	echo "Fetching data from Elasticsearch..."; \
	curl -s "$(ES_HOST)/$(ES_INDEX)/_search?scroll=5m&size=1000" -H 'Content-Type: application/json' -d '{"query":{"match_all":{}}}' > /tmp/es_backup_tmp.json; \
	if [ $$? -ne 0 ]; then \
		echo "Error: Failed to connect to Elasticsearch"; \
		rm -f /tmp/es_backup_tmp.json; \
		exit 1; \
	fi; \
	scroll_id=$$(cat /tmp/es_backup_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('_scroll_id', ''))" 2>/dev/null); \
	cat /tmp/es_backup_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); [print(json.dumps(hit)) for hit in data.get('hits', {}).get('hits', [])]" > "$$BACKUP_FILE"; \
	total=$$(cat /tmp/es_backup_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('hits', {}).get('total', {}).get('value', 0))" 2>/dev/null); \
	if [ -n "$$scroll_id" ] && [ "$$scroll_id" != "null" ]; then \
		echo "Fetching remaining data..."; \
		while true; do \
			curl -s "$(ES_HOST)/_search/scroll" -H 'Content-Type: application/json' -d "{\"scroll\":\"5m\",\"scroll_id\":\"$$scroll_id\"}" > /tmp/es_scroll_tmp.json; \
			hits=$$(cat /tmp/es_scroll_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('hits', {}).get('hits', [])))" 2>/dev/null); \
			if [ "$$hits" = "0" ]; then \
				break; \
			fi; \
			cat /tmp/es_scroll_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); [print(json.dumps(hit)) for hit in data.get('hits', {}).get('hits', [])]" >> "$$BACKUP_FILE"; \
			scroll_id=$$(cat /tmp/es_scroll_tmp.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('_scroll_id', ''))" 2>/dev/null); \
		done; \
		curl -s -X DELETE "$(ES_HOST)/_search/scroll" -H 'Content-Type: application/json' -d "{\"scroll_id\":\"$$scroll_id\"}" > /dev/null; \
	fi; \
	rm -f /tmp/es_backup_tmp.json /tmp/es_scroll_tmp.json; \
	doc_count=$$(wc -l < "$$BACKUP_FILE" | tr -d ' '); \
	file_size=$$(du -h "$$BACKUP_FILE" | cut -f1); \
	echo ""; \
	echo "✓ Backup completed successfully!"; \
	echo "  File: $$BACKUP_FILE"; \
	echo "  Documents: $$doc_count"; \
	echo "  Size: $$file_size"

restore:
	@echo "Available backups:"
	@echo ""
	@ls -lh "$(BACKUP_DIR)"/*.json 2>/dev/null || echo "No backups found in $(BACKUP_DIR)/"
	@echo ""
	@read -p "Enter backup filename (from $(BACKUP_DIR)/): " backup_file; \
	if [ -z "$$backup_file" ]; then \
		echo "No filename provided. Cancelled."; \
		exit 1; \
	fi; \
	BACKUP_PATH="$(BACKUP_DIR)/$$backup_file"; \
	if [ ! -f "$$BACKUP_PATH" ]; then \
		echo "Error: Backup file not found: $$BACKUP_PATH"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "WARNING: This will delete all existing data in $(ES_INDEX) index!"; \
	read -p "Are you sure you want to restore from $$backup_file? [y/N] " -n 1 -r; \
	echo; \
	if [[ ! $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Cancelled."; \
		exit 0; \
	fi; \
	echo "Deleting existing index..."; \
	curl -s -X DELETE "$(ES_HOST)/$(ES_INDEX)" > /dev/null 2>&1; \
	echo "Restoring data from $$BACKUP_PATH..."; \
	count=0; \
	while IFS= read -r line; do \
		if [ -n "$$line" ]; then \
			doc_id=$$(echo "$$line" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('_id', ''))" 2>/dev/null); \
			source=$$(echo "$$line" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('_source', {})))" 2>/dev/null); \
			if [ -n "$$doc_id" ] && [ "$$source" != "{}" ]; then \
				curl -s -X POST "$(ES_HOST)/$(ES_INDEX)/_doc/$$doc_id" -H 'Content-Type: application/json' -d "$$source" > /dev/null; \
				count=$$((count + 1)); \
				if [ $$((count % 100)) -eq 0 ]; then \
					echo "  Restored $$count documents..."; \
				fi; \
			fi; \
		fi; \
	done < "$$BACKUP_PATH"; \
	echo ""; \
	echo "✓ Restore completed successfully!"; \
	echo "  Total documents restored: $$count"

list-backups:
	@echo "Available Elasticsearch backups:"
	@echo "================================="
	@if [ -d "$(BACKUP_DIR)" ] && [ -n "$$(ls -A $(BACKUP_DIR)/*.json 2>/dev/null)" ]; then \
		for backup in $(BACKUP_DIR)/*.json; do \
			filename=$$(basename "$$backup"); \
			size=$$(du -h "$$backup" | cut -f1); \
			lines=$$(wc -l < "$$backup" | tr -d ' '); \
			timestamp=$$(echo "$$filename" | sed 's/telegram_messages_\([0-9]*_[0-9]*\)\.json/\1/' | sed 's/_/ /'); \
			echo "📦 $$filename"; \
			echo "   Size: $$size | Documents: $$lines | Created: $$timestamp"; \
			echo ""; \
		done; \
	else \
		echo "No backups found in $(BACKUP_DIR)/"; \
		echo "Run 'make backup' to create a backup."; \
	fi

query:
	@if [ -z "$(KEYWORD)" ]; then \
		echo "Error: KEYWORD is required"; \
		echo "Usage: make query KEYWORD=<keyword> N=<number>"; \
		echo "Example: make query KEYWORD=bitcoin N=5"; \
		exit 1; \
	fi
	@N=$${N:-10}; \
	echo "Searching for '$(KEYWORD)' (top $$N results)..."; \
	echo ""; \
	curl -s "$(ES_HOST)/$(ES_INDEX)/_search" -H 'Content-Type: application/json' -d '{"query":{"multi_match":{"query":"$(KEYWORD)","fields":["text","channel_title","sender_name"]}},"size":'$$N',"sort":[{"_score":{"order":"desc"}},{"timestamp":{"order":"desc"}}]}' | python3 -m json.tool
