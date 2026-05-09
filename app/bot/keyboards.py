from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Портфель"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🚀 Запустить торговлю"), KeyboardButton(text="🛑 Остановить торговлю")],
            [KeyboardButton(text="📈 История сделок"), KeyboardButton(text="ℹ️ Рекомендации/Инфо")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_settings_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Добавить API ключи", callback_data="add_api_keys")],
            [InlineKeyboardButton(text="🛠 Стратегия и Риски", callback_data="config_strategy")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_exchange_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Binance", callback_data="exch_binance"),
             InlineKeyboardButton(text="Bybit", callback_data="exch_bybit")],
            [InlineKeyboardButton(text="OKX", callback_data="exch_okx"),
             InlineKeyboardButton(text="Tinkoff", callback_data="exch_tinkoff")]
        ]
    )
    return keyboard

def get_strategies_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Автоматическая (Рекомендуется)", callback_data="strat_auto")],
            [InlineKeyboardButton(text="Сеточная (Grid - Флэт)", callback_data="strat_grid")],
            [InlineKeyboardButton(text="Трендовая (SMA/MACD)", callback_data="strat_trend")],
            [InlineKeyboardButton(text="DCA (Усреднение)", callback_data="strat_dca")]
        ]
    )
    return keyboard
