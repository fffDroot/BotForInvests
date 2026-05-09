import pandas as pd
import ta

class MarketAnalyzer:
    @staticmethod
    def get_comprehensive_technical_analysis(df: pd.DataFrame) -> dict:
        """
        Returns a dict of indicators: RSI, Bollinger Bands, Volume trend, MACD.
        """
        if df.empty or len(df) < 50:
            return {"status": "insufficient_data"}

        rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]

        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]
        current_price = df['close'].iloc[-1]

        macd = ta.trend.MACD(df['close'])
        macd_line = macd.macd().iloc[-1]
        macd_signal = macd.macd_signal().iloc[-1]

        # Determine signals
        rsi_signal = "oversold" if rsi < 30 else ("overbought" if rsi > 70 else "neutral")
        bb_signal = "lower_band" if current_price <= bb_low else ("upper_band" if current_price >= bb_high else "middle")
        macd_signal_str = "bullish" if macd_line > macd_signal else "bearish"

        return {
            "status": "ok",
            "rsi": rsi,
            "rsi_signal": rsi_signal,
            "bb_signal": bb_signal,
            "macd_signal": macd_signal_str
        }

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
