import ccxt.async_support as ccxt
import logging
import asyncio
from typing import List

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, exchange_id: str = 'binance'):
        self.exchange_id = exchange_id

    async def get_top_volume_coins(self, limit: int = 5) -> List[str]:
        """
        Fetches symbols with highest trading volume.
        """
        exchange_class = getattr(ccxt, self.exchange_id)
        exchange = exchange_class({'enableRateLimit': True})

        try:
            tickers = await exchange.fetch_tickers()
            # Filter USDT pairs
            usdt_pairs = {k: v for k, v in tickers.items() if k.endswith('/USDT')}

            # Sort by quote volume descending
            sorted_pairs = sorted(usdt_pairs.items(), key=lambda item: item[1].get('quoteVolume', 0) or 0, reverse=True)

            # Extract top N symbols
            top_symbols = [pair[0] for pair in sorted_pairs[:limit]]
            return top_symbols
        except Exception as e:
            logger.error(f"Error scanning market on {self.exchange_id}: {e}")
            return []
        finally:
            await exchange.close()
