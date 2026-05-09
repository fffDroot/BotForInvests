from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
import json

from .keyboards import get_main_menu, get_settings_menu, get_exchange_menu, get_strategies_menu, get_ai_menu
from .states import ExchangeAuth, StrategyConfig, LLMAuth
from app.db.database import AsyncSessionLocal
from app.db.models import User, ExchangeAPIKey, TradingSettings, TradeHistory, LLMAPIKey
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
    await message.answer("Меню настроек:", reply_markup=get_settings_menu())

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery):
    await callback.message.edit_text("Меню настроек:", reply_markup=get_settings_menu())

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
        api_keys = await session.execute(select(ExchangeAPIKey).where(ExchangeAPIKey.user_id == user.id))
        api_keys = api_keys.scalars().all()

    if not api_keys:
        await message.answer("Сначала добавьте API ключи бирж в настройках.")
        return

    await message.answer("⏳ Собираю информацию по балансам...")
    from app.exchanges.factory import get_exchange_wrapper

    portfolio_text = "📊 **Ваш портфель:**\n\n"
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

@router.message(F.text == "ℹ️ Рекомендации/Инфо")
async def show_info(message: Message):
    info_text = (
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
