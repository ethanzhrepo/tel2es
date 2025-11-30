# Telegram Scraper - Docker Deployment

This directory contains the Docker deployment configuration for the Telegram Scraper.

## Usage Guide

### 1. Clone and Enter Directory

```bash
git clone <repository_url>
cd tel2es/docker
```

### 2. Build Images

Build the Docker images for the scraper and API server.

```bash
make build
```

### 3. Login to Telegram

You need to authenticate with your Telegram account. This step will generate a session file.

```bash
make login
```

**Configuration Details:**
When you run `make login`, the script will check for a `config/config.yml` file. If it doesn't exist, it will create one from the example.

You will be prompted to enter your **API credentials**:
1.  **API ID & API Hash**:
    *   Go to [https://my.telegram.org/apps](https://my.telegram.org/apps).
    *   Log in with your phone number.
    *   Click on "API development tools".
    *   Create a new application (if you haven't already).
    *   Copy the `App api_id` and `App api_hash`.
2.  **Phone Number**: Enter your phone number in international format (e.g., `+1234567890`).

After entering these details, the script will ask for the **verification code** sent to your Telegram app (or via SMS).

### 4. Configure Channels

Select which Telegram channels or groups you want to monitor.

```bash
make config
```

This command opens an interactive Terminal User Interface (TUI):
*   **List**: Shows all dialogs (groups/channels) your account is part of.
*   **Navigate**: Use `Up`/`Down` arrows or `Tab`.
*   **Select/Deselect**: Press `Space` to toggle monitoring for a channel.
*   **Save**: Press `F8` to save your selection.
*   **Exit**: Press `ESC` to exit without saving.

### 5. Start Services

Start the Elasticsearch, Scraper, and API services in the background.

```bash
make start
```

### 6. Stop Services

Stop all running services.

```bash
make stop
```

## Other Commands

### Monitoring & Maintenance

*   **View Logs**:
    ```bash
    make logs       # View scraper logs
    make logs-api   # View API logs
    make logs-all   # View all logs
    ```

*   **Check Health**:
    ```bash
    make health     # Check status of Elasticsearch, API, and containers
    ```

*   **Clean Data**:
    ```bash
    make clean      # Stop services and remove all data volumes (WARNING: Destructive)
    ```

### Data Management

*   **Backup Data**:
    ```bash
    make backup     # Create a snapshot of Elasticsearch data to ./backups
    ```

*   **Restore Data**:
    ```bash
    make restore    # Restore data from a backup file in ./backups
    ```

*   **List Backups**:
    ```bash
    make list-backups
    ```

*   **Quick Search**:
    ```bash
    make query KEYWORD=bitcoin N=5  # Search for 'bitcoin', show top 5 results
    ```

## Directory Structure

*   `Makefile`: Helper commands for easy management.
*   `docker-compose-with-es.yml`: Docker Compose configuration.
*   `config/`: Contains configuration files and session data.
*   `data/`: Persistent storage for Elasticsearch (created after start).
*   `backups/`: Storage for data backups.
