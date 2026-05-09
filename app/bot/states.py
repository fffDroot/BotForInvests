from aiogram.fsm.state import State, StatesGroup

class ExchangeAuth(StatesGroup):
    waiting_for_exchange_name = State()
    waiting_for_api_key = State()
    waiting_for_api_secret = State()
    waiting_for_passphrase = State()

class StrategyConfig(StatesGroup):
    waiting_for_strategy = State()
    waiting_for_risk_pct = State()

class LLMAuth(StatesGroup):
    waiting_for_provider_name = State()
    waiting_for_api_key = State()

class WatchlistConfig(StatesGroup):
    waiting_for_symbol = State()

class PaperTopUp(StatesGroup):
    waiting_for_asset = State()
    waiting_for_amount = State()
