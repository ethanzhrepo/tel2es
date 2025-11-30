import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
import re

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)

class CoinGeckoSymbolMatcher:
    """CoinGecko API数字货币符号匹配器"""

    def __init__(self):
        self.symbols_data: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0
        self.fetch_interval = 3600  # 1小时（秒）
        self.api_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"

    async def _fetch_symbols(self) -> List[Dict[str, Any]]:
        """从CoinGecko API获取数字货币数据"""
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp 不可用，无法获取CoinGecko数据")
            return []

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"从CoinGecko获取到 {len(data)} 个数字货币")
                        return data
                    else:
                        logger.error(f"CoinGecko API请求失败: HTTP {response.status}")
                        return []
        except asyncio.TimeoutError:
            logger.error("CoinGecko API请求超时")
            return []
        except Exception as e:
            logger.error(f"获取CoinGecko数据失败: {e}")
            return []

    async def _ensure_data_fresh(self):
        """确保数据是最新的（每小时刷新一次）"""
        current_time = time.time()
        if current_time - self.last_fetch_time > self.fetch_interval or not self.symbols_data:
            logger.info("正在从CoinGecko刷新数字货币数据...")
            new_data = await self._fetch_symbols()
            if new_data:  # 只有成功获取数据时才更新
                self.symbols_data = new_data
                self.last_fetch_time = current_time
                logger.info(f"CoinGecko数据刷新成功，共 {len(self.symbols_data)} 个数字货币")
            elif not self.symbols_data:  # 如果是首次获取失败
                logger.warning("首次获取CoinGecko数据失败，将使用空数据")

    async def find_symbols_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        在文本中查找匹配的数字货币symbol和name

        Args:
            text: 要搜索的文本

        Returns:
            匹配到的数字货币数据列表，每个元素包含完整的CoinGecko API响应数据
        """
        if not text:
            return []

        await self._ensure_data_fresh()

        if not self.symbols_data:
            logger.debug("CoinGecko数据为空，跳过符号匹配")
            return []

        # 清理文本：移除URL和邮箱地址，避免误匹配
        cleaned_text = self._clean_text_for_matching(text)

        found_symbols = []
        text_upper = cleaned_text.upper()

        # 创建已匹配symbol的集合，避免重复
        matched_symbols = set()

        for coin_data in self.symbols_data:
            symbol = coin_data.get('symbol', '').upper()
            name = coin_data.get('name', '').upper()
            coin_id = coin_data.get('id', '')

            # 匹配symbol (作为独立单词，大小写不敏感)
            if symbol and len(symbol) >= 2:  # 只匹配至少2个字符的symbol
                pattern = r'\b' + re.escape(symbol) + r'\b'
                if re.search(pattern, text_upper) and symbol not in matched_symbols:
                    found_symbols.append(coin_data)
                    matched_symbols.add(symbol)
                    logger.debug(f"匹配到symbol: {symbol} -> {coin_data.get('name')}")
                    continue

            # 匹配name (作为独立单词，大小写不敏感)
            if name and len(name) >= 3:  # 只匹配至少3个字符的name
                # 对于复合词名称，分别匹配每个词
                name_words = name.split()
                if len(name_words) == 1:
                    # 单词名称直接匹配
                    pattern = r'\b' + re.escape(name) + r'\b'
                    if re.search(pattern, text_upper) and coin_id not in [s.get('id') for s in found_symbols]:
                        found_symbols.append(coin_data)
                        logger.debug(f"匹配到name: {name} -> {coin_data.get('symbol')}")
                else:
                    # 复合词名称匹配完整短语
                    pattern = r'\b' + re.escape(name) + r'\b'
                    if re.search(pattern, text_upper) and coin_id not in [s.get('id') for s in found_symbols]:
                        found_symbols.append(coin_data)
                        logger.debug(f"匹配到复合name: {name} -> {coin_data.get('symbol')}")

        logger.debug(f"在文本中找到 {len(found_symbols)} 个匹配的数字货币")
        return found_symbols

    def _clean_text_for_matching(self, text: str) -> str:
        """
        清理文本，移除URL和邮箱地址，避免误匹配

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # URL 匹配模式（更全面的匹配）
        url_patterns = [
            r'https?://[^\s]+',  # http/https URLs
            r'www\.[^\s]+',      # www URLs
            r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',  # 域名格式
        ]

        # 邮箱匹配模式
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        # 文件扩展名模式（避免匹配.html, .com等）
        file_extension_pattern = r'\b\w+\.[a-zA-Z]{2,4}\b'

        cleaned_text = text

        # 移除URL
        for pattern in url_patterns:
            cleaned_text = re.sub(pattern, ' ', cleaned_text, flags=re.IGNORECASE)

        # 移除邮箱地址
        cleaned_text = re.sub(email_pattern, ' ', cleaned_text)

        # 移除文件扩展名（如 .html, .com 等）
        cleaned_text = re.sub(file_extension_pattern, ' ', cleaned_text)

        # 移除多余的空格
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        logger.debug(f"文本清理: '{text[:100]}...' -> '{cleaned_text[:100]}...'")
        return cleaned_text

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息（用于调试）"""
        return {
            'cached_symbols_count': len(self.symbols_data),
            'last_fetch_time': self.last_fetch_time,
            'time_until_next_refresh': max(0, self.fetch_interval - (time.time() - self.last_fetch_time)),
            'aiohttp_available': AIOHTTP_AVAILABLE
        }

# 全局实例
_symbol_matcher = CoinGeckoSymbolMatcher()

async def find_crypto_symbols(text: str) -> List[Dict[str, Any]]:
    """
    在文本中查找匹配的数字货币symbol和name

    Args:
        text: 要搜索的文本

    Returns:
        匹配到的数字货币数据列表，每个元素包含完整的CoinGecko API响应数据

    Example:
        >>> import asyncio
        >>> symbols = asyncio.run(find_crypto_symbols("BTC is going to the moon! ETHEREUM looks bullish"))
        >>> print([s['symbol'] for s in symbols])
        ['btc', 'eth']
    """
    return await _symbol_matcher.find_symbols_in_text(text)

def get_symbol_cache_info() -> Dict[str, Any]:
    """
    获取符号缓存信息

    Returns:
        包含缓存状态的字典
    """
    return _symbol_matcher.get_cache_info()
