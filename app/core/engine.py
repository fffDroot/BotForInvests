import asyncio
import logging
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, ExchangeAPIKey, TradingSettings, TradeHistory, LLMAPIKey
from app.exchanges.factory import get_exchange_wrapper
from app.strategies.factory import get_strategy
from app.strategies.news import NewsAnalyzer
from app.strategies.llm_council import LLMCouncil
from app.bot.config import bot

logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self):
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info("Trading engine started.")
        while self.is_running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Error in engine cycle: {e}")
            await asyncio.sleep(60) # Run every minute

    async def stop(self):
        self.is_running = False
        logger.info("Trading engine stopped.")

    async def _run_cycle(self):
        async with AsyncSessionLocal() as session:
            # Get all users with enabled trading
            result = await session.execute(select(TradingSettings).where(TradingSettings.is_trading_enabled == True))
            active_settings_list = result.scalars().all()

            for settings in active_settings_list:
                await self._process_user(session, settings)

    async def _get_global_sentiment(self, session, user: User, settings: TradingSettings) -> str:
        """Returns 'positive', 'neutral', or 'negative' based on News/LLM Council"""
        analyzer = NewsAnalyzer()
        news = analyzer.fetch_latest_news(limit=10)

        if settings.use_llm_council:
            llm_keys = await session.execute(select(LLMAPIKey).where(LLMAPIKey.user_id == user.id))
            keys_list = [{"provider": k.provider_name, "key": k.api_key} for k in llm_keys.scalars().all()]
            if keys_list:
                council = LLMCouncil(keys_list)
                news_text = "\n".join(news)
                decision = await council.get_council_decision(news_text)
                return decision.get('sentiment', 'neutral')

        # Fallback to baseline
        baseline = analyzer.analyze_sentiment(news)
        return baseline.get('label', 'neutral')

    async def _process_user(self, session, settings: TradingSettings):
        user = await session.scalar(select(User).where(User.id == settings.user_id))
        api_keys = await session.execute(select(ExchangeAPIKey).where(ExchangeAPIKey.user_id == user.id))
        api_keys = api_keys.scalars().all()

        if not api_keys:
            return # No keys to trade with

        # Get global sentiment once per user cycle
        global_sentiment = await self._get_global_sentiment(session, user, settings)

        for api_key_info in api_keys:
            try:
                await self._trade_on_exchange(session, user, settings, api_key_info, global_sentiment)
            except Exception as e:
                logger.error(f"Error trading for user {user.id} on {api_key_info.exchange_name}: {e}")

    async def _trade_on_exchange(self, session, user: User, settings: TradingSettings, api_key_info: ExchangeAPIKey, global_sentiment: str):
        exchange = get_exchange_wrapper(
            exchange_name=api_key_info.exchange_name,
            api_key=api_key_info.api_key,
            api_secret=api_key_info.api_secret,
            passphrase=api_key_info.passphrase
        )

        # Basic pairs for demo purposes based on exchange
        symbol = 'BTC/USDT' if api_key_info.exchange_name != 'tinkoff' else 'BBG004730N88' # SBER figi as example

        # 1. Fetch Market Data
        df = await exchange.get_ohlcv(symbol, timeframe='1h')
        if df is None or df.empty:
            await exchange.close()
            return

        # 2. Get Strategy
        strategy = get_strategy(
            strategy_name=settings.strategy_mode,
            settings={
                'max_risk_per_trade_pct': settings.max_risk_per_trade_pct,
                'strategy_params': settings.strategy_params
            },
            market_df=df
        )

        # 3. Get Balances / Position
        balances = await exchange.get_balance()
        base_asset = symbol.split('/')[0] if '/' in symbol else symbol
        quote_asset = symbol.split('/')[1] if '/' in symbol else 'RUB' # simple fallback

        current_position = balances.get(base_asset, 0.0)
        quote_balance = balances.get(quote_asset, 0.0)

        # 4. Synthesize signals with global sentiment
        # Do not buy if world is crashing
        signal = strategy.generate_signal(df, current_position)

        if signal and signal['action'] == 'buy' and global_sentiment == 'negative':
            logger.info(f"Skipping BUY for {user.id} on {symbol} due to negative global sentiment.")
            signal = None # Suppress buy signal

        # Optional: Panic sell if world is crashing and we hold positions
        if current_position > 0 and global_sentiment == 'negative' and not signal:
            logger.info(f"Generating panic SELL for {user.id} on {symbol} due to negative global sentiment.")
            signal = {'action': 'sell', 'reason': 'Global negative sentiment (Panic Sell)', 'size_pct': 100.0}

        if signal:
            await self._execute_signal(session, user, settings, exchange, symbol, signal, current_position, quote_balance)

            # Save strategy params if modified by strategy (like Grid)
            if 'save_last_buy' in signal:
                params = settings.strategy_params or {}
                params['last_buy_price'] = signal['save_last_buy']
                settings.strategy_params = params
                await session.commit()

        await exchange.close()

    async def _execute_signal(self, session, user: User, settings: TradingSettings, exchange, symbol: str, signal: dict, current_position: float, quote_balance: float):
        action = signal['action']
        size_pct = signal['size_pct'] / 100.0

        amount = 0.0
        if action == 'buy':
            # Buy using a percentage of available quote balance (e.g. USDT)
            if quote_balance <= 0:
                return
            # Need current price to calculate amount
            df = await exchange.get_ohlcv(symbol, limit=1)
            if df.empty: return
            current_price = df['close'].iloc[-1]

            spend_amount = quote_balance * size_pct
            amount = spend_amount / current_price

        elif action == 'sell':
            # Sell a percentage of current holdings
            if current_position <= 0:
                return
            amount = current_position * size_pct

        if amount <= 0:
            return

        # Simple risk management check
        if action == 'buy' and size_pct * 100 > settings.max_risk_per_trade_pct:
             logger.warning(f"Risk limit exceeded for user {user.id}. Requested {size_pct*100}%, allowed {settings.max_risk_per_trade_pct}%")
             return

        # Execute Order
        order = await exchange.create_market_order(symbol, action, amount)

        if order:
            price = order.get('price') or order.get('average') or 0.0 # Extract from order response
            if price == 0.0:
                 # Fallback to current market price if order obj doesn't have it
                 df = await exchange.get_ohlcv(symbol, limit=1)
                 price = df['close'].iloc[-1] if not df.empty else 0.0

            # Record Trade
            trade = TradeHistory(
                user_id=user.id,
                exchange=exchange.__class__.__name__,
                symbol=symbol,
                side=action,
                amount=amount,
                price=price,
                strategy_used=settings.strategy_mode,
                status='closed'
            )
            session.add(trade)
            await session.commit()

            # Send Notification
            msg = f"🔔 **Сигнал исполнен!**\n\n" \
                  f"**Биржа:** {exchange.__class__.__name__}\n" \
                  f"**Пара:** {symbol}\n" \
                  f"**Действие:** {'Покупка 🟢' if action == 'buy' else 'Продажа 🔴'}\n" \
                  f"**Количество:** {amount:.4f}\n" \
                  f"**Цена:** {price:.4f}\n" \
                  f"**Стратегия:** {settings.strategy_mode}\n" \
                  f"**Причина:** {signal.get('reason', '')}"
            try:
                await bot.send_message(user.telegram_id, msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send tg notification: {e}")

engine = TradingEngine()
