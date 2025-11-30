"""
Unit tests for MessageExtractor
"""

import pytest
import asyncio
from src.extractor import MessageExtractor


class TestMessageExtractor:
    """Test message data extraction"""

    @pytest.fixture
    def extractor(self):
        return MessageExtractor()

    @pytest.mark.asyncio
    async def test_extract_ethereum_address(self, extractor):
        """Test Ethereum address extraction"""
        text = "Send to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
        result = await extractor.extract_data(text)

        assert 'addresses' in result
        assert 'ethereum' in result['addresses']
        assert len(result['addresses']['ethereum']) == 1
        assert result['addresses']['ethereum'][0] == '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0'

    @pytest.mark.asyncio
    async def test_extract_bitcoin_address(self, extractor):
        """Test Bitcoin address extraction"""
        text = "BTC address: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
        result = await extractor.extract_data(text)

        assert 'addresses' in result
        assert 'bitcoin' in result['addresses']
        assert len(result['addresses']['bitcoin']) > 0

    @pytest.mark.asyncio
    async def test_extract_urls(self, extractor):
        """Test URL extraction"""
        text = "Check out https://dexscreener.com/ethereum/0x123"
        result = await extractor.extract_data(text)

        assert 'urls' in result
        assert len(result['urls']) == 1
        assert result['urls'][0]['domain'] == 'dexscreener.com'
        assert result['urls'][0]['type'] == 'dex_tracker'

    @pytest.mark.asyncio
    async def test_sentiment_positive(self, extractor):
        """Test positive sentiment detection"""
        text = "BTC is pumping to the moon! Bullish!"
        result = await extractor.extract_data(text)

        assert 'sentiment' in result
        assert result['sentiment'] == 'positive'
        assert 'pump' in result['keywords']
        assert 'moon' in result['keywords']

    @pytest.mark.asyncio
    async def test_sentiment_negative(self, extractor):
        """Test negative sentiment detection"""
        text = "Market is dumping hard, bearish trend"
        result = await extractor.extract_data(text)

        assert 'sentiment' in result
        assert result['sentiment'] == 'negative'
        assert 'dump' in result['keywords']

    @pytest.mark.asyncio
    async def test_sentiment_neutral(self, extractor):
        """Test neutral sentiment detection"""
        text = "Trading volume analysis shows support at $50k"
        result = await extractor.extract_data(text)

        assert 'sentiment' in result
        assert result['sentiment'] == 'neutral'

    @pytest.mark.asyncio
    async def test_extract_prices(self, extractor):
        """Test price extraction"""
        text = "BTC at $45000 and ETH at 3000 USDT"
        result = await extractor.extract_data(text)

        assert 'prices' in result
        assert len(result['prices']) >= 1
        assert any(p['price'] == 45000 for p in result['prices'])

    @pytest.mark.asyncio
    async def test_empty_text(self, extractor):
        """Test handling of empty text"""
        result = await extractor.extract_data("")

        assert result == {}

    @pytest.mark.asyncio
    async def test_clean_text_for_matching(self, extractor):
        """Test text cleaning"""
        text = "Check https://example.com and email@test.com for info"
        cleaned = extractor._clean_text_for_matching(text)

        assert 'https://example.com' not in cleaned
        assert 'email@test.com' not in cleaned
