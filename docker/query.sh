#!/bin/bash
# Query script for Telegram message search
# Usage: ./query.sh "search text" [topn]
# Example: ./query.sh "bitcoin" 20

# Check if query text is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <query_text> [topn]"
    echo "Example: $0 \"bitcoin\" 20"
    exit 1
fi

# Parameters
QUERY_TEXT="$1"
TOPN="${2:-10}"  # Default to 10 if not specified

# API endpoint
API_URL="http://localhost:8000/search"

# URL encode the query text
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$QUERY_TEXT'''))")

# Make API request
echo "Searching for: $QUERY_TEXT (limit: $TOPN)"
echo "----------------------------------------"

curl -s "${API_URL}?keywords=${ENCODED_QUERY}&limit=${TOPN}" | python3 -m json.tool

# Alternative: If you want formatted output, uncomment below and comment above
# curl -s "${API_URL}?keywords=${ENCODED_QUERY}&limit=${TOPN}" | \
#   python3 -c "
# import sys, json
# data = json.load(sys.stdin)
# print(f\"Total results: {data['total']}\")
# print(f\"Showing: {len(data['hits'])} messages\n\")
# for i, hit in enumerate(data['hits'], 1):
#     print(f\"{i}. [{hit['timestamp']}] {hit['chat_title']}\")
#     if hit.get('username'):
#         print(f\"   From: @{hit['username']} ({hit.get('first_name', 'N/A')})\")
#     print(f\"   Text: {hit['text'][:200]}{'...' if len(hit['text']) > 200 else ''}\")
#     if hit.get('score'):
#         print(f\"   Score: {hit['score']:.4f}\")
#     print()
# "
