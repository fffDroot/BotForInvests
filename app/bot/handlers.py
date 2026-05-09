from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
import json

from .keyboards import get_main_menu, get_settings_menu, get_exchange_menu, get_strategies_menu, get_ai_menu
from .states import ExchangeAuth, StrategyConfig, LLMAuth, WatchlistConfig
from app.db.database import AsyncSessionLocal
from app.db.models import User, ExchangeAPIKey, TradingSettings, TradeHistory, LLMAPIKey, Watchlist
from app.strategies.news import NewsAnalyzer
from app.strategies.llm_council import LLMCouncil

router = Router()

@router.message(Command("start"))
async def start_cmd(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user:
            new_user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(new_user)
            await session.commit()

            # create default settings
            settings = TradingSettings(user_id=new_user.id)
            session.add(settings)
            await session.commit()

    welcome_text = (
        "Привет! Я ваш автономный торговый бот. 🤖\n\n"
        "Я могу торговать на различных биржах используя продвинутые алгоритмы.\n"
        "Чтобы начать:\n"
        "1. Перейдите в настройки и добавьте API ключи\n"
        "2. Выберите стратегию\n"
        "3. Запустите торговлю\n"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        await message.answer("Меню настроек:", reply_markup=get_settings_menu(settings.trade_mode, settings.account_type))

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        await callback.message.edit_text("Меню настроек:", reply_markup=get_settings_menu(settings.trade_mode, settings.account_type))

@router.callback_query(F.data == "manage_watchlist")
async def manage_watchlist(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        watchlist_result = await session.execute(select(Watchlist).where(Watchlist.user_id == user.id))
        watchlist = [w.symbol for w in watchlist_result.scalars().all()]

    text = "📋 **Ваш Watchlist:**\n"
    if watchlist:
        text += "\n".join(f"- {s}" for s in watchlist)
    else:
        text += "Пусто. Бот будет искать монеты автоматически."

    text += "\n\nОтправьте мне тикер, который хотите добавить или удалить (например, BTC/USDT или SBER):"

    await callback.message.edit_text(text)
    await state.set_state(WatchlistConfig.waiting_for_symbol)

@router.message(WatchlistConfig.waiting_for_symbol)
async def process_watchlist_symbol(message: Message, state: FSMContext):
    symbol = message.text.upper().strip()

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))

        existing = await session.scalar(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == symbol))
        if existing:
            await session.delete(existing)
            action_text = f"🗑 Удалено: {symbol}"
        else:
            new_item = Watchlist(user_id=user.id, symbol=symbol, asset_type='auto')
            session.add(new_item)
            action_text = f"✅ Добавлено: {symbol}"

        await session.commit()

    await message.answer(action_text)
    await state.clear()

@router.callback_query(F.data == "close_settings")
async def close_settings(callback: CallbackQuery):
    await callback.message.delete()

@router.callback_query(F.data == "toggle_trade_mode")
async def toggle_trade_mode(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        settings.trade_mode = "auto" if settings.trade_mode == "advisory" else "advisory"
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_menu(settings.trade_mode, settings.account_type))

@router.callback_query(F.data == "toggle_account_type")
async def toggle_account_type(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        settings.account_type = "real" if settings.account_type == "paper" else "paper"
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_menu(settings.trade_mode, settings.account_type))

@router.callback_query(F.data == "add_api_keys")
async def add_api_keys_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите биржу для подключения:", reply_markup=get_exchange_menu())
    await state.set_state(ExchangeAuth.waiting_for_exchange_name)

@router.callback_query(ExchangeAuth.waiting_for_exchange_name, F.data.startswith("exch_"))
async def add_api_key_exchange_chosen(callback: CallbackQuery, state: FSMContext):
    exchange_name = callback.data.split("_")[1]
    await state.update_data(exchange_name=exchange_name)
    await callback.message.edit_text(f"Отлично. Отправьте ваш API KEY для {exchange_name.capitalize()}:")
    await state.set_state(ExchangeAuth.waiting_for_api_key)

@router.message(ExchangeAuth.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext):
    await state.update_data(api_key=message.text)

    # Tinkoff only needs a token (which we treat as api_key), others need secret
    data = await state.get_data()
    if data['exchange_name'] == 'tinkoff':
        await save_api_keys(message, state)
    else:
        await message.answer("Теперь отправьте ваш API SECRET:")
        await state.set_state(ExchangeAuth.waiting_for_api_secret)

@router.message(ExchangeAuth.waiting_for_api_secret)
async def process_api_secret(message: Message, state: FSMContext):
    await state.update_data(api_secret=message.text)
    data = await state.get_data()

    if data['exchange_name'] == 'okx':
        await message.answer("Для OKX также требуется Passphrase. Отправьте его:")
        await state.set_state(ExchangeAuth.waiting_for_passphrase)
    else:
        await save_api_keys(message, state)

@router.message(ExchangeAuth.waiting_for_passphrase)
async def process_passphrase(message: Message, state: FSMContext):
    await state.update_data(passphrase=message.text)
    await save_api_keys(message, state)

async def save_api_keys(message: Message, state: FSMContext):
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))

        # remove old key for this exchange if exists
        old_key = await session.scalar(select(ExchangeAPIKey).where(
            ExchangeAPIKey.user_id == user.id,
            ExchangeAPIKey.exchange_name == data['exchange_name']
        ))
        if old_key:
            await session.delete(old_key)

        new_key = ExchangeAPIKey(
            user_id=user.id,
            exchange_name=data['exchange_name'],
            api_key=data.get('api_key'),
            api_secret=data.get('api_secret'),
            passphrase=data.get('passphrase')
        )
        session.add(new_key)
        await session.commit()

    await message.answer(f"✅ Ключи для {data['exchange_name'].capitalize()} успешно сохранены!")
    await state.clear()

@router.callback_query(F.data == "config_strategy")
async def config_strategy_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите торговую стратегию:", reply_markup=get_strategies_menu())
    await state.set_state(StrategyConfig.waiting_for_strategy)

@router.callback_query(StrategyConfig.waiting_for_strategy, F.data.startswith("strat_"))
async def process_strategy_choice(callback: CallbackQuery, state: FSMContext):
    strategy = callback.data.split("_")[1]
    await state.update_data(strategy=strategy)
    await callback.message.edit_text("Введите максимальный риск на сделку в процентах (например: 1.5):")
    await state.set_state(StrategyConfig.waiting_for_risk_pct)

@router.message(StrategyConfig.waiting_for_risk_pct)
async def process_risk_pct(message: Message, state: FSMContext):
    try:
        risk = float(message.text)
        if risk <= 0 or risk > 100:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от 0.01 до 100")
        return

    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        settings.strategy_mode = data['strategy']
        settings.max_risk_per_trade_pct = risk
        await session.commit()

    await message.answer(f"✅ Стратегия '{data['strategy']}' и риск {risk}% сохранены.")
    await state.clear()

@router.message(F.text == "🚀 Запустить торговлю")
async def start_trading(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        settings.is_trading_enabled = True
        await session.commit()
    await message.answer("🟢 Торговля запущена! Бот начал анализировать рынок.")

@router.message(F.text == "🛑 Остановить торговлю")
async def stop_trading(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        settings.is_trading_enabled = False
        await session.commit()
    await message.answer("🔴 Торговля остановлена. Новые ордера открываться не будут.")

@router.message(F.text == "📊 Портфель")
async def show_portfolio(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        api_keys = await session.execute(select(ExchangeAPIKey).where(ExchangeAPIKey.user_id == user.id))
        api_keys = api_keys.scalars().all()

    if not api_keys and settings.account_type != 'paper':
        await message.answer("Сначала добавьте API ключи бирж в настройках.")
        return

    await message.answer("⏳ Собираю информацию по балансам...")
    from app.exchanges.factory import get_exchange_wrapper
    from app.exchanges.paper import PaperTradingExchangeWrapper

    portfolio_text = f"📊 **Ваш портфель ({'Виртуальный' if settings.account_type == 'paper' else 'Реальный'}):**\n\n"

    # Initial mock balances for paper trading
    INITIAL_USDT = 10000.0
    total_usdt_value = 0.0

    if settings.account_type == 'paper':
        exchange = PaperTradingExchangeWrapper(user_id=user.id)
        balances = await exchange.get_balance()
        portfolio_text += f"🏛 **Paper Wallet**:\n"
        has_funds = False

        for asset, amount in balances.items():
            if amount > 0:
                portfolio_text += f"🔹 {asset}: {amount:.4f}\n"
                has_funds = True
                if asset == 'USDT':
                    total_usdt_value += amount
                elif asset != 'RUB':
                    # Rough PnL calculation: convert asset back to USDT
                    df = await exchange.get_ohlcv(f"{asset}/USDT", limit=1)
                    if df is not None and not df.empty:
                        price = df['close'].iloc[-1]
                        total_usdt_value += amount * price

        if not has_funds:
            portfolio_text += "Пусто\n"

        # PnL logic for Paper
        pnl = total_usdt_value - INITIAL_USDT
        pnl_pct = (pnl / INITIAL_USDT) * 100
        emoji = "📈" if pnl >= 0 else "📉"
        portfolio_text += f"\n{emoji} **Прибыль/Убыток (PnL):** {pnl:.2f} USDT ({pnl_pct:.2f}%)\n"
    else:
        for key in api_keys:
            try:
                exchange = get_exchange_wrapper(key.exchange_name, key.api_key, key.api_secret, key.passphrase)
                balances = await exchange.get_balance()
                await exchange.close()

                portfolio_text += f"🏛 **{key.exchange_name.upper()}**:\n"
                has_funds = False
                for asset, amount in balances.items():
                    if amount > 0: # Simple threshold
                        portfolio_text += f"🔹 {asset}: {amount:.4f}\n"
                        has_funds = True
                if not has_funds:
                    portfolio_text += "Пусто\n"
                portfolio_text += "\n"
            except Exception as e:
                portfolio_text += f"🏛 **{key.exchange_name.upper()}**: Ошибка получения ({e})\n\n"

    await message.answer(portfolio_text, parse_mode="Markdown")

@router.message(F.text == "📈 История сделок")
async def show_history(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        trades_result = await session.execute(
            select(TradeHistory).where(TradeHistory.user_id == user.id).order_by(TradeHistory.timestamp.desc()).limit(10)
        )
        trades = trades_result.scalars().all()

    if not trades:
        await message.answer("История сделок пуста.")
        return

    history_text = "📈 **Последние 10 сделок:**\n\n"
    for t in trades:
        action = "🟢 Покупка" if t.side == 'buy' else "🔴 Продажа"
        date_str = t.timestamp.strftime("%Y-%m-%d %H:%M")
        history_text += f"{date_str} | {action} {t.symbol}\n"
        history_text += f"Кол-во: {t.amount:.4f} | Цена: {t.price:.4f}\n"
        history_text += f"Стратегия: {t.strategy_used}\n\n"

    await message.answer(history_text, parse_mode="Markdown")

@router.callback_query(F.data.startswith("exec_"))
async def execute_advisory_trade(callback: CallbackQuery):
    action_data = callback.data.split("_")

    if action_data[1] == "reject":
        await callback.message.edit_text(callback.message.text + "\n\n❌ **Отклонено пользователем.**")
        return

    side = action_data[1]
    symbol = action_data[2]
    size_pct = float(action_data[3])

    await callback.message.edit_text(callback.message.text + "\n\n⏳ **Выполняю...**")

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        api_key_info = await session.scalar(select(ExchangeAPIKey).where(ExchangeAPIKey.user_id == user.id)) # Simplified for demo, grabs first key

        if not api_key_info:
            await callback.message.edit_text("❌ Ошибка: нет API ключей.")
            return

        from app.core.engine import engine
        from app.exchanges.paper import PaperTradingExchangeWrapper
        from app.exchanges.factory import get_exchange_wrapper

        if settings.account_type == "paper":
            exchange = PaperTradingExchangeWrapper(user_id=user.id, mock_exchange_name=api_key_info.exchange_name)
        else:
            exchange = get_exchange_wrapper(
                exchange_name=api_key_info.exchange_name,
                api_key=api_key_info.api_key,
                api_secret=api_key_info.api_secret,
                passphrase=api_key_info.passphrase
            )

        balances = await exchange.get_balance()
        base_asset = symbol.split('/')[0] if '/' in symbol else symbol
        quote_asset = symbol.split('/')[1] if '/' in symbol else 'USDT'

        current_position = balances.get(base_asset, 0.0)
        quote_balance = balances.get(quote_asset, 0.0)

        signal = {'action': side, 'size_pct': size_pct * 100, 'reason': 'Manual Advisory Approval'}

        # Execute manually via engine's method
        await engine._execute_signal(session, user, settings, exchange, symbol, signal, current_position, quote_balance)
        await exchange.close()

    await callback.message.edit_text(callback.message.text.replace("⏳ **Выполняю...**", "✅ **Сделка отправлена на биржу!**"))

@router.callback_query(F.data == "config_ai")
async def config_ai_menu(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        await callback.message.edit_text(
            "Настройки ИИ и Консилиума.\nКонсилиум использует подключенные LLM модели для анализа новостей.",
            reply_markup=get_ai_menu(settings.use_llm_council)
        )

@router.callback_query(F.data == "toggle_council")
async def toggle_council(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))
        settings.use_llm_council = not settings.use_llm_council
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_ai_menu(settings.use_llm_council))

@router.callback_query(F.data == "add_llm_key")
async def add_llm_key_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название провайдера (например, openai, anthropic, deepseek):")
    await state.set_state(LLMAuth.waiting_for_provider_name)

@router.message(LLMAuth.waiting_for_provider_name)
async def process_llm_provider(message: Message, state: FSMContext):
    provider = message.text.lower().strip()
    await state.update_data(provider=provider)
    await message.answer(f"Отлично. Отправьте ваш API KEY для {provider}:")
    await state.set_state(LLMAuth.waiting_for_api_key)

@router.message(LLMAuth.waiting_for_api_key)
async def process_llm_api_key(message: Message, state: FSMContext):
    data = await state.get_data()
    api_key = message.text.strip()
    provider = data['provider']

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))

        old_key = await session.scalar(select(LLMAPIKey).where(
            LLMAPIKey.user_id == user.id,
            LLMAPIKey.provider_name == provider
        ))
        if old_key:
            await session.delete(old_key)

        new_key = LLMAPIKey(user_id=user.id, provider_name=provider, api_key=api_key)
        session.add(new_key)
        await session.commit()

    await message.answer(f"✅ Ключ для LLM {provider} успешно сохранен!")
    await state.clear()

@router.message(Command("rebalance"))
async def rebalance_portfolio(message: Message):
    await message.answer("⚖️ Начинаю анализ портфеля для ребалансировки...")
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        api_keys = await session.execute(select(ExchangeAPIKey).where(ExchangeAPIKey.user_id == user.id))
        api_keys = api_keys.scalars().all()
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        if not api_keys and settings.account_type != "paper":
            await message.answer("Нет подключенных бирж.")
            return

        from app.exchanges.factory import get_exchange_wrapper
        from app.exchanges.paper import PaperTradingExchangeWrapper

        portfolio_str = ""

        if settings.account_type == "paper":
            exchange = PaperTradingExchangeWrapper(user_id=user.id, mock_exchange_name='paper')
            balances = await exchange.get_balance()
            portfolio_str += f"Paper Wallet: {balances}\n"
        else:
            for key in api_keys:
                try:
                    exchange = get_exchange_wrapper(key.exchange_name, key.api_key, key.api_secret, key.passphrase)
                    balances = await exchange.get_balance()
                    await exchange.close()
                    non_zero = {k: v for k, v in balances.items() if v > 0}
                    portfolio_str += f"{key.exchange_name}: {non_zero}\n"
                except Exception:
                    pass

        analyzer = NewsAnalyzer()
        news = analyzer.fetch_latest_news(limit=5)
        news_text = "\n".join(news)

        if settings.use_llm_council:
            llm_keys = await session.execute(select(LLMAPIKey).where(LLMAPIKey.user_id == user.id))
            keys_list = [{"provider": k.provider_name, "key": k.api_key} for k in llm_keys.scalars().all()]
            if keys_list:
                council = LLMCouncil(keys_list)
                prompt = f"Мой текущий портфель: {portfolio_str}. Текущие мировые новости: {news_text}. Предложи конкретные шаги по ребалансировке с учетом рисков."
                decision = await council.get_council_decision(prompt)

                await message.answer(f"⚖️ **План Ребалансировки (ИИ Консилиум)**\n\nСентимент: {decision['sentiment'].upper()}\n\nРекомендации:\n{decision['reasoning']}", parse_mode="Markdown")
                return

        await message.answer("Консилиум ИИ выключен или нет ключей. Для умной ребалансировки включите LLM в настройках.")

@router.message(F.text == "🌍 Анализ рынка и мира")
async def analyze_world(message: Message):
    await message.answer("⏳ Собираю свежие новости и анализирую мировой фон...")

    analyzer = NewsAnalyzer()
    news = analyzer.fetch_latest_news(limit=10)
    news_text = "\n".join(news)

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        if settings.use_llm_council:
            llm_keys = await session.execute(select(LLMAPIKey).where(LLMAPIKey.user_id == user.id))
            keys_list = [{"provider": k.provider_name, "key": k.api_key} for k in llm_keys.scalars().all()]

            council = LLMCouncil(keys_list)
            decision = await council.get_council_decision(news_text)

            text = f"🌍 **Глобальный фон (Консилиум ИИ)**\n"
            text += f"**Сентимент:** {decision['sentiment'].upper()} (Score: {decision['score']:.2f})\n"
            text += f"**Количество моделей:** {decision['council_size']}\n\n"
            text += f"{decision['reasoning']}\n\n"
        else:
            baseline = analyzer.analyze_sentiment(news)
            text = f"🌍 **Глобальный фон (Базовый NLP)**\n"
            text += f"**Сентимент:** {baseline['label'].upper()} (Score: {baseline['score']:.2f})\n"
            text += f"{baseline['summary']}\n\n"

    await message.answer(text, parse_mode="Markdown")

@router.message(F.text.regexp(r"^[A-Z0-9]+(/[A-Z0-9]+)?$"))
async def deep_dive_analysis(message: Message):
    symbol = message.text.upper()
    await message.answer(f"🔍 Начинаю глубокий анализ актива **{symbol}**...")

    from app.exchanges.factory import get_exchange_wrapper
    from app.strategies.analyzer import MarketAnalyzer

    # We need to fetch OHLCV. Use paper exchange for anonymous public fetch
    from app.exchanges.paper import PaperTradingExchangeWrapper

    exchange = PaperTradingExchangeWrapper(user_id=message.from_user.id, mock_exchange_name='binance')
    df = await exchange.get_ohlcv(symbol, timeframe='1d', limit=100)

    if df is None or df.empty:
        await message.answer(f"❌ Не удалось получить данные графика для {symbol}. Проверьте правильность тикера.")
        return

    tech_analysis = MarketAnalyzer.get_comprehensive_technical_analysis(df)
    trend = MarketAnalyzer.determine_market_phase(df)

    current_price = df['close'].iloc[-1]

    # News and AI Council
    analyzer = NewsAnalyzer()
    news = analyzer.fetch_latest_news(limit=5)

    # Simulate adding specific ticker to news query conceptually (in a real app, feed parser would be queried specifically)
    news.append(f"Анализ актива {symbol} показывает текущую цену {current_price}.")

    news_text = "\n".join(news)

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        settings = await session.scalar(select(TradingSettings).where(TradingSettings.user_id == user.id))

        council_text = ""
        if settings.use_llm_council:
            llm_keys = await session.execute(select(LLMAPIKey).where(LLMAPIKey.user_id == user.id))
            keys_list = [{"provider": k.provider_name, "key": k.api_key} for k in llm_keys.scalars().all()]

            if keys_list:
                council = LLMCouncil(keys_list)
                # Specific prompt for asset
                decision = await council.get_council_decision(f"Проанализируй перспективы {symbol}. Текущие новости: {news_text}")
                council_text = f"\n🧠 **Мнение ИИ Консилиума:**\nСентимент: {decision['sentiment'].upper()}\nОбоснование:\n{decision['reasoning']}\n"

    report = f"📊 **Глубокий анализ {symbol}**\n\n" \
             f"**Текущая цена:** {current_price:.4f}\n" \
             f"**Тренд:** {trend.upper()}\n" \
             f"**RSI:** {tech_analysis.get('rsi', 0):.2f} ({tech_analysis.get('rsi_signal', 'unknown')})\n" \
             f"**MACD Signal:** {tech_analysis.get('macd_signal', 'unknown')}\n" \
             f"**Полосы Боллинджера:** {tech_analysis.get('bb_signal', 'unknown')}\n"

    if council_text:
        report += council_text

    await message.answer(report, parse_mode="Markdown")

@router.message(F.text == "ℹ️ Рекомендации/Инфо")
async def show_info(message: Message):
    info_text = (
        "📚 **Инструкция и возможности:**\n\n"
        "🔸 **Глубокий анализ:** Просто отправьте тикер (например, `BTC/USDT` или `AAPL`), и бот проведет его глубокий анализ через ИИ Консилиум и индикаторы.\n"
        "🔸 **Ребалансировка:** Отправьте команду `/rebalance`, чтобы ИИ проанализировал ваш портфель и дал советы по перераспределению средств.\n\n"
        "📚 **Справка по стратегиям:**\n\n"
        "🔹 **Автоматическая**: Бот анализирует рынок (трендовые индикаторы ADX/MACD) и сам выбирает "
        "лучшую стратегию. Идеально для пассивного инвестирования.\n\n"
        "🔹 **Сеточная (Grid)**: Бот расставляет сетку ордеров на покупку ниже текущей цены и сетку на продажу выше. "
        "Зарабатывает на колебаниях цены (флэт). Плохо работает при сильном падении.\n\n"
        "🔹 **Трендовая**: Покупка при подтверждении восходящего тренда, продажа при развороте.\n\n"
        "🔹 **DCA**: Постепенная покупка актива равными частями при падении для усреднения цены входа.\n\n"
        "⚠️ **Риск-менеджмент**: Обязательно настраивайте % риска! Не храните все средства на одном аккаунте."
    )
    await message.answer(info_text, parse_mode="Markdown")
