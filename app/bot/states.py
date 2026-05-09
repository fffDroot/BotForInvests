from aiogram.fsm.state import State, StatesGroup

class ExchangeAuth(StatesGroup):
    waiting_for_exchange_name = State()
    waiting_for_api_key = State()
    waiting_for_api_secret = State()
    waiting_for_passphrase = State()

class StrategyConfig(StatesGroup):
    waiting_for_strategy = State()
    waiting_for_risk_pct = State()
