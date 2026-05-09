from tinkoff.invest import AsyncClient, OrderDirection, OrderType
from tinkoff.invest.utils import quotation_to_decimal
from datetime import timedelta, datetime
import pandas as pd

class TinkoffExchangeWrapper:
    def __init__(self, token: str):
        self.token = token
        # Client needs to be managed properly, usually within an async with block.
        # This wrapper might need adjustments depending on how it's called.

    async def get_balance(self) -> dict:
        async with AsyncClient(self.token) as client:
            accounts = await client.users.get_accounts()
            if not accounts.accounts:
                return {}
            account_id = accounts.accounts[0].id
            portfolio = await client.operations.get_portfolio(account_id=account_id)

            balance = {}
            for position in portfolio.positions:
                amount = quotation_to_decimal(position.quantity)
                balance[position.figi] = float(amount)
            return balance

    async def get_ohlcv(self, figi: str, timeframe='1h', limit=100) -> pd.DataFrame:
        # Mapping timeframe to tinkoff CandleInterval
        from tinkoff.invest import CandleInterval

        interval_map = {
            '1m': CandleInterval.CANDLE_INTERVAL_1_MIN,
            '5m': CandleInterval.CANDLE_INTERVAL_5_MIN,
            '15m': CandleInterval.CANDLE_INTERVAL_15_MIN,
            '1h': CandleInterval.CANDLE_INTERVAL_HOUR,
            '1d': CandleInterval.CANDLE_INTERVAL_DAY,
        }

        interval = interval_map.get(timeframe, CandleInterval.CANDLE_INTERVAL_HOUR)

        # Calculate from/to
        now = datetime.utcnow()
        if timeframe.endswith('h'):
            from_time = now - timedelta(hours=int(timeframe[:-1]) * limit)
        elif timeframe.endswith('d'):
            from_time = now - timedelta(days=int(timeframe[:-1]) * limit)
        else:
            from_time = now - timedelta(days=1) # default fallback

        async with AsyncClient(self.token) as client:
            candles = await client.market_data.get_candles(
                figi=figi,
                from_=from_time,
                to=now,
                interval=interval
            )

            data = []
            for c in candles.candles:
                data.append({
                    'timestamp': c.time,
                    'open': float(quotation_to_decimal(c.open)),
                    'high': float(quotation_to_decimal(c.high)),
                    'low': float(quotation_to_decimal(c.low)),
                    'close': float(quotation_to_decimal(c.close)),
                    'volume': c.volume
                })

            df = pd.DataFrame(data)
            return df

    async def create_market_order(self, figi: str, side: str, amount: int) -> dict:
        direction = OrderDirection.ORDER_DIRECTION_BUY if side.lower() == 'buy' else OrderDirection.ORDER_DIRECTION_SELL

        async with AsyncClient(self.token) as client:
            accounts = await client.users.get_accounts()
            account_id = accounts.accounts[0].id

            import uuid
            order_id = str(uuid.uuid4())

            try:
                order = await client.orders.post_order(
                    figi=figi,
                    quantity=amount,
                    direction=direction,
                    account_id=account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    order_id=order_id
                )
                return {
                    'id': order.order_id,
                    'status': 'closed', # Market orders are usually filled immediately
                    'side': side,
                    'amount': amount,
                    'symbol': figi
                }
            except Exception as e:
                print(f"Error placing Tinkoff order: {e}")
                return None

    async def close(self):
        pass
