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

    async def get_orderbook_and_funding(self, symbol: str) -> dict:
        """
        Fetches Orderbook Imbalance and Funding Rates (if applicable)
        to predict short term price action.
        """
        exchange_class = getattr(ccxt, self.exchange_id)
        exchange = exchange_class({'enableRateLimit': True})

        result = {"orderbook_imbalance": "neutral", "funding_rate": "N/A", "open_interest": "N/A"}

        try:
            # 1. Orderbook Analysis
            ob = await exchange.fetch_order_book(symbol, limit=50)
            bids = sum([x[1] for x in ob['bids']]) # Total volume of buyers
            asks = sum([x[1] for x in ob['asks']]) # Total volume of sellers

            if bids > asks * 1.5:
                result['orderbook_imbalance'] = "bullish (strong buy wall)"
            elif asks > bids * 1.5:
                result['orderbook_imbalance'] = "bearish (strong sell wall)"

            # 2. Funding Rates / Futures Analysis (Only works on derivatives markets, wrapping in try/except)
            if exchange.has.get('fetchFundingRate'):
                try:
                    funding = await exchange.fetch_funding_rate(symbol)
                    rate = funding.get('fundingRate', 0)
                    if rate is not None:
                        if rate > 0.001: # High funding
                            result['funding_rate'] = f"{rate:.4f} (High - Squeeze Risk)"
                        elif rate < -0.001:
                            result['funding_rate'] = f"{rate:.4f} (Negative - Short Squeeze Risk)"
                        else:
                            result['funding_rate'] = f"{rate:.4f} (Normal)"
                except Exception:
                    pass # Not all pairs/exchanges support this

        except Exception as e:
            logger.error(f"Error fetching orderbook/funding for {symbol}: {e}")
        finally:
            await exchange.close()

        return result
