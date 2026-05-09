from .implementations import TrendStrategy, GridStrategy, DCAStrategy
from .analyzer import MarketAnalyzer
import pandas as pd
from typing import Dict, Any, Optional

def get_strategy(strategy_name: str, settings: Dict[str, Any], market_df: Optional[pd.DataFrame] = None) -> Any:
    strategy_name = strategy_name.lower()

    if strategy_name == 'auto' and market_df is not None:
        phase = MarketAnalyzer.determine_market_phase(market_df)
        if phase == 'trending':
            return TrendStrategy(settings)
        else:
            return GridStrategy(settings)

    if strategy_name == 'grid':
        return GridStrategy(settings)
    elif strategy_name == 'trend':
        return TrendStrategy(settings)
    elif strategy_name == 'dca':
        return DCAStrategy(settings)

    # Default fallback
    return TrendStrategy(settings)
