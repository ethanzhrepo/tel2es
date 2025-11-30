"""
Message Data Extractor for Telegram Scraper
Extracts crypto addresses, symbols, URLs, sentiment, and other structured data
"""

import re
import logging
from typing import Dict, Any, List
import emoji

from symbol_util import find_crypto_symbols

logger = logging.getLogger(__name__)


class MessageExtractor:
    """Message content extractor for crypto and structured data"""

    # Regex patterns
    ETHEREUM_ADDRESS = re.compile(r'0x[a-fA-F0-9]{40}')
    SOLANA_ADDRESS = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')
    BITCOIN_ADDRESS = re.compile(r'(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}')
    SYMBOL_PATTERN = re.compile(r'\b[A-Z]{2,10}\b')
    URL_PATTERN = re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?')
    PRICE_PATTERN = re.compile(r'\$?(\d+(?:\.\d+)?)\s*(?:USD|USDT|USDC|\$)', re.IGNORECASE)

    # Sentiment keywords
    BULLISH_KEYWORDS = {'pump', 'moon', 'bullish', 'buy', 'long', 'rocket', 'up', 'rise', 'gain'}
    BEARISH_KEYWORDS = {'dump', 'bear', 'bearish', 'sell', 'short', 'crash', 'down', 'fall', 'loss'}
    NEUTRAL_KEYWORDS = {'analysis', 'chart', 'support', 'resistance', 'volume', 'trading'}

    async def extract_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from message text"""
        if not text:
            return {}

        # Remove emojis to get raw text
        raw_text = emoji.demojize(text)

        # Extract crypto addresses
        addresses = {
            'ethereum': list(set(self.ETHEREUM_ADDRESS.findall(text))),
            'solana': list(set(addr for addr in self.SOLANA_ADDRESS.findall(text)
                               if self._is_valid_solana_address(addr))),
            'bitcoin': list(set(self.BITCOIN_ADDRESS.findall(text)))
        }

        # Use CoinGecko API to match crypto symbols and names
        try:
            crypto_matches = await find_crypto_symbols(text)
            # Extract simple symbol list (backwards compatibility)
            symbols = [match.get('symbol', '').upper() for match in crypto_matches]
            # Also save complete crypto information
            crypto_data = crypto_matches
        except Exception as e:
            logger.error(f"CoinGecko symbol matching failed: {e}")
            # Fallback to simple regex matching with cleaned text
            cleaned_text = self._clean_text_for_matching(text)
            symbols = list(set(self.SYMBOL_PATTERN.findall(cleaned_text.upper())))
            crypto_data = []

        # If CoinGecko didn't match anything, try simple regex as fallback
        if not symbols:
            cleaned_text = self._clean_text_for_matching(text)
            fallback_symbols = list(set(self.SYMBOL_PATTERN.findall(cleaned_text.upper())))
            symbols = fallback_symbols

        # Extract URLs
        urls = []
        for url in self.URL_PATTERN.findall(text):
            urls.append({
                'url': url,
                'domain': self._extract_domain(url),
                'type': self._classify_url(url)
            })

        # Extract prices
        prices = []
        for match in self.PRICE_PATTERN.finditer(text):
            prices.append({
                'price': float(match.group(1)),
                'currency': 'USD'
            })

        # Keyword analysis
        text_lower = text.lower()
        keywords = []
        sentiment = 'neutral'

        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)

        if bullish_count > bearish_count:
            sentiment = 'positive'
        elif bearish_count > bullish_count:
            sentiment = 'negative'

        # Extract matched keywords
        all_keywords = self.BULLISH_KEYWORDS | self.BEARISH_KEYWORDS | self.NEUTRAL_KEYWORDS
        keywords = [kw for kw in all_keywords if kw in text_lower]

        return {
            'addresses': addresses,
            'symbols': symbols,
            'crypto_currencies': crypto_data,
            'urls': urls,
            'prices': prices,
            'keywords': keywords,
            'sentiment': sentiment,
            'raw_text': raw_text
        }

    def _is_valid_solana_address(self, addr: str) -> bool:
        """Validate Solana address format"""
        return 32 <= len(addr) <= 44 and addr.isalnum()

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ''

    def _classify_url(self, url: str) -> str:
        """Classify URL type"""
        domain = self._extract_domain(url).lower()

        if any(dex in domain for dex in ['dexscreener', 'dextools', 'birdeye']):
            return 'dex_tracker'
        elif any(explorer in domain for explorer in ['etherscan', 'solscan', 'blockchain']):
            return 'blockchain_explorer'
        elif any(exchange in domain for exchange in ['binance', 'coinbase', 'okx']):
            return 'exchange'
        elif any(social in domain for social in ['twitter', 'telegram', 'discord']):
            return 'social_media'
        else:
            return 'unknown'

    def _clean_text_for_matching(self, text: str) -> str:
        """
        Clean text by removing URLs and email addresses to avoid false matches

        Args:
            text: Original text

        Returns:
            Cleaned text
        """
        # URL patterns (comprehensive matching)
        url_patterns = [
            r'https?://[^\s]+',  # http/https URLs
            r'www\.[^\s]+',      # www URLs
            r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',  # domain format
        ]

        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        # File extension pattern (avoid matching .html, .com etc)
        file_extension_pattern = r'\b\w+\.[a-zA-Z]{2,4}\b'

        cleaned_text = text

        # Remove URLs
        for pattern in url_patterns:
            cleaned_text = re.sub(pattern, ' ', cleaned_text, flags=re.IGNORECASE)

        # Remove email addresses
        cleaned_text = re.sub(email_pattern, ' ', cleaned_text)

        # Remove file extensions (like .html, .com etc)
        cleaned_text = re.sub(file_extension_pattern, ' ', cleaned_text)

        # Remove extra whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        return cleaned_text
