import pandas as pd
import ta

class MarketAnalyzer:
    @staticmethod
    def determine_market_phase(df: pd.DataFrame) -> str:
        """
        Determines market phase: 'trending' or 'ranging' (flat).
        Uses ADX (Average Directional Index).
        ADX > 25 indicates a strong trend.
        ADX <= 25 indicates a ranging market.
        """
        if df.empty or len(df) < 14:
            return "unknown"

        adx_indicator = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        adx_value = adx_indicator.adx().iloc[-1]

        if pd.isna(adx_value):
            return "unknown"

        if adx_value > 25:
            return "trending"
        else:
            return "ranging"

    @staticmethod
    def get_trend_direction(df: pd.DataFrame) -> str:
        """
        Determines trend direction using SMA(50) and SMA(200)
        """
        if df.empty or len(df) < 200:
            return "unknown"

        sma50 = ta.trend.sma_indicator(df['close'], window=50).iloc[-1]
        sma200 = ta.trend.sma_indicator(df['close'], window=200).iloc[-1]
        current_price = df['close'].iloc[-1]

        if current_price > sma50 and sma50 > sma200:
            return "up"
        elif current_price < sma50 and sma50 < sma200:
            return "down"
        else:
            return "neutral"
