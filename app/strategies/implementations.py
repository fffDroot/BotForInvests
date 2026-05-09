from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Dict, Any

class BaseStrategy(ABC):
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, current_position: float) -> Optional[Dict[str, Any]]:
        """
        Analyzes data and returns a trading signal.
        Returns None if no action is needed.
        Returns dict like: {'action': 'buy'/'sell', 'reason': 'str', 'size_pct': float}
        """
        pass

class TrendStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy
    Buys when fast MA crosses above slow MA.
    Sells when fast MA crosses below slow MA.
    """
    def generate_signal(self, df: pd.DataFrame, current_position: float) -> Optional[Dict[str, Any]]:
        if len(df) < 50:
            return None

        # Calculate MAs
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()

        prev_fast = df['sma20'].iloc[-2]
        prev_slow = df['sma50'].iloc[-2]
        curr_fast = df['sma20'].iloc[-1]
        curr_slow = df['sma50'].iloc[-1]

        # Golden Cross (Buy)
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            if current_position <= 0:
                return {'action': 'buy', 'reason': 'Golden Cross (Trend Up)', 'size_pct': self.settings.get('max_risk_per_trade_pct', 1.0)}

        # Death Cross (Sell)
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            if current_position > 0:
                return {'action': 'sell', 'reason': 'Death Cross (Trend Down)', 'size_pct': 100.0} # sell all

        return None

class GridStrategy(BaseStrategy):
    """
    Simplified Grid Strategy for ranging markets.
    Assumes grid levels are calculated based on current price +- grid_spacing_pct
    """
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(settings)
        strat_params = settings.get('strategy_params') or {}
        self.grid_spacing_pct = strat_params.get('grid_spacing_pct', 1.0) / 100.0
        self.last_buy_price = strat_params.get('last_buy_price', 0.0)

    def generate_signal(self, df: pd.DataFrame, current_position: float) -> Optional[Dict[str, Any]]:
        if df.empty:
            return None

        current_price = df['close'].iloc[-1]

        if current_position <= 0 or self.last_buy_price == 0:
            # Initial entry
            return {'action': 'buy', 'reason': 'Grid Initial Entry', 'size_pct': self.settings.get('max_risk_per_trade_pct', 1.0), 'save_last_buy': current_price}

        # Check if price dropped enough for next grid buy
        if current_price <= self.last_buy_price * (1 - self.grid_spacing_pct):
            return {'action': 'buy', 'reason': 'Grid Level Buy', 'size_pct': self.settings.get('max_risk_per_trade_pct', 1.0), 'save_last_buy': current_price}

        # Check if price increased enough for grid sell (take profit)
        if current_price >= self.last_buy_price * (1 + self.grid_spacing_pct):
            return {'action': 'sell', 'reason': 'Grid Level Sell', 'size_pct': 100.0, 'save_last_buy': 0.0} # reset grid

        return None

class DCAStrategy(BaseStrategy):
    """
    Dollar Cost Averaging: buys fixed amount regularly regardless of price.
    For this implementation, we simulate it by buying if enough time passed or price dropped.
    """
    def generate_signal(self, df: pd.DataFrame, current_position: float) -> Optional[Dict[str, Any]]:
        # Simplified DCA: just buy a small percentage if price drops by 5% from high
        if df.empty or len(df) < 20:
            return None

        recent_high = df['high'].rolling(20).max().iloc[-1]
        current_price = df['close'].iloc[-1]

        if current_price <= recent_high * 0.95:
             return {'action': 'buy', 'reason': 'DCA Buy (Price dip)', 'size_pct': self.settings.get('max_risk_per_trade_pct', 1.0)}

        return None
