from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import PaperWallet

class PaperTradingExchangeWrapper:
    def __init__(self, user_id: int, mock_exchange_name: str = 'paper'):
        self.user_id = user_id
        self.mock_exchange_name = mock_exchange_name

    async def get_balance(self) -> dict:
        async with AsyncSessionLocal() as session:
            wallets = await session.execute(
                select(PaperWallet).where(PaperWallet.user_id == self.user_id)
            )
            balances = {w.asset: w.balance for w in wallets.scalars().all()}

            # Default fallback for testing if user has no paper wallet setup yet
            if not balances:
                balances = {"USDT": 10000.0, "RUB": 1000000.0}
            return balances

    async def get_ohlcv(self, symbol: str, timeframe='1h', limit=100):
        # We still need real market data to trade on paper
        import ccxt.async_support as ccxt
        import pandas as pd

        # Determine if it's a crypto pair or a stock/FIGI (simple heuristic)
        if '/' in symbol:
            try:
                # Use binance or original exchange if available via ccxt
                exchange_id = self.mock_exchange_name if hasattr(ccxt, self.mock_exchange_name) else 'binance'
                exchange_class = getattr(ccxt, exchange_id)
                exchange = exchange_class({'enableRateLimit': True})
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                await exchange.close()
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                return None
        else:
            # It's likely a Tinkoff FIGI. We need token for real Tinkoff data.
            # But since this is paper, and we might not have a Tinkoff token globally,
            # we simulate/stub or use yahoo finance as fallback if implemented.
            # For this MVP, we return a fallback df.
            return pd.DataFrame({'close': [100.0, 101.0, 102.0]}) # Stub for Tinkoff paper

    async def create_market_order(self, symbol: str, side: str, amount: float) -> dict:
        # Mocking an execution using current market price
        df = await self.get_ohlcv(symbol, limit=1)
        if df is None or df.empty:
             return None

        current_price = df['close'].iloc[-1]
        base_asset = symbol.split('/')[0] if '/' in symbol else symbol
        quote_asset = symbol.split('/')[1] if '/' in symbol else 'USDT'

        total_cost = amount * current_price

        async with AsyncSessionLocal() as session:
             # Get or create wallets
             base_wallet = await session.scalar(select(PaperWallet).where(PaperWallet.user_id == self.user_id, PaperWallet.asset == base_asset))
             quote_wallet = await session.scalar(select(PaperWallet).where(PaperWallet.user_id == self.user_id, PaperWallet.asset == quote_asset))

             if not base_wallet:
                 base_wallet = PaperWallet(user_id=self.user_id, asset=base_asset, balance=0.0)
                 session.add(base_wallet)
             if not quote_wallet:
                 quote_wallet = PaperWallet(user_id=self.user_id, asset=quote_asset, balance=10000.0) # default initial
                 session.add(quote_wallet)

             if side == 'buy':
                 if quote_wallet.balance < total_cost:
                      return None # Insufficient paper funds
                 quote_wallet.balance -= total_cost
                 base_wallet.balance += amount
             elif side == 'sell':
                 if base_wallet.balance < amount:
                      return None
                 base_wallet.balance -= amount
                 quote_wallet.balance += total_cost

             await session.commit()

        import uuid
        return {
            'id': str(uuid.uuid4()),
            'status': 'closed',
            'side': side,
            'amount': amount,
            'price': current_price,
            'symbol': symbol
        }

    async def close(self):
        pass
