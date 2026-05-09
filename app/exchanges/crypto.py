import ccxt.async_support as ccxt
from typing import Dict, Any, List
import pandas as pd

class CryptoExchangeWrapper:
    def __init__(self, exchange_id: str, api_key: str, secret: str, passphrase: str = None):
        exchange_class = getattr(ccxt, exchange_id)

        config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        }
        if passphrase:
            config['password'] = passphrase

        self.exchange = exchange_class(config)

    async def get_balance(self) -> Dict[str, float]:
        try:
            balance = await self.exchange.fetch_balance()
            return balance.get('total', {})
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return {}

    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        try:
            order = await self.exchange.create_market_order(symbol, side, amount)
            return order
        except Exception as e:
            print(f"Error creating order: {e}")
            return None

    async def close(self):
        await self.exchange.close()
