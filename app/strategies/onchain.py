import aiohttp
import logging
from typing import List

logger = logging.getLogger(__name__)

class OnChainAnalyzer:
    """
    Simulates checking for whale activity.
    In a real app, this would connect to Whale Alert API or a mempool tracker.
    """
    def __init__(self):
        # We could use public blockchain APIs here
        pass

    async def get_whale_activity_summary(self) -> str:
        """
        Returns a string describing recent massive transfers.
        """
        # For MVP, we simulate fetching an anomaly.
        try:
            # Simulated data for demonstration
            anomalies = [
                "15,000 BTC переведено с неизвестного кошелька на Binance (возможен дамп).",
                "100,000,000 USDT напечатано в сети Tron (возможен памп)."
            ]

            summary = "\n".join([f"- {a}" for a in anomalies])
            if summary:
                return f"Активность китов (On-Chain):\n{summary}"
            return "Аномальной активности китов не обнаружено."

        except Exception as e:
            logger.error(f"Error fetching on-chain data: {e}")
            return "Данные On-Chain недоступны."
