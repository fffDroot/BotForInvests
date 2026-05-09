from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    api_keys = relationship("ExchangeAPIKey", back_populates="user", cascade="all, delete")
    llm_keys = relationship("LLMAPIKey", back_populates="user", cascade="all, delete")
    settings = relationship("TradingSettings", back_populates="user", uselist=False, cascade="all, delete")
    trades = relationship("TradeHistory", back_populates="user", cascade="all, delete")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete")
    paper_wallet = relationship("PaperWallet", back_populates="user", cascade="all, delete")

class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String) # e.g., BTC/USDT, SBER
    asset_type = Column(String) # crypto, stock

    user = relationship("User", back_populates="watchlist")

class PaperWallet(Base):
    __tablename__ = "paper_wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    asset = Column(String) # USDT, BTC, RUB
    balance = Column(Float, default=0.0)

    user = relationship("User", back_populates="paper_wallet")

class LLMAPIKey(Base):
    __tablename__ = "llm_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider_name = Column(String) # openai, anthropic, deepseek, groq, gemini, etc.
    api_key = Column(String)
    assigned_role = Column(String, default="general") # general, fundamental, technical, risk
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="llm_keys")

class ExchangeAPIKey(Base):
    __tablename__ = "exchange_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange_name = Column(String) # binance, bybit, tinkoff, etc.
    api_key = Column(String)
    api_secret = Column(String, nullable=True)
    passphrase = Column(String, nullable=True) # needed for some exchanges like OKX
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="api_keys")

class TradingSettings(Base):
    __tablename__ = "trading_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    is_trading_enabled = Column(Boolean, default=False)
    strategy_mode = Column(String, default="auto") # auto, grid, dca, trend
    trade_mode = Column(String, default="advisory") # auto, advisory
    account_type = Column(String, default="paper") # real, paper

    # Risk Management
    max_risk_per_trade_pct = Column(Float, default=1.0)
    global_stop_loss_pct = Column(Float, default=10.0)
    take_profit_pct = Column(Float, default=2.0)
    use_trailing_stop = Column(Boolean, default=True)
    trailing_stop_pct = Column(Float, default=3.0)

    # Optional JSON field for strategy specific settings (e.g. grid spacing)
    strategy_params = Column(JSON, nullable=True)

    # AI and Council Settings
    use_llm_council = Column(Boolean, default=False)
    council_mode = Column(String, default="classic") # classic, role_based

    # Smart Features
    smart_alerts_enabled = Column(Boolean, default=True)
    whale_tracking_enabled = Column(Boolean, default=False)
    auto_averaging_enabled = Column(Boolean, default=False)

    user = relationship("User", back_populates="settings")

class TradeHistory(Base):
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange = Column(String)
    symbol = Column(String)
    side = Column(String) # buy or sell
    amount = Column(Float)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    strategy_used = Column(String)
    pnl = Column(Float, nullable=True) # Profit and Loss if closed
    status = Column(String, default="closed")

    user = relationship("User", back_populates="trades")
