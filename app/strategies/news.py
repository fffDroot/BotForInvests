import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import logging

logger = logging.getLogger(__name__)

class NewsAnalyzer:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        # RSS feeds covering general world news, economy, and crypto
        self.rss_urls = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,BTC-USD",
            "https://cointelegraph.com/rss",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html", # CNBC Top News
            "https://www.investing.com/rss/news_25.rss" # Forex & Macro
        ]

    def fetch_latest_news(self, limit: int = 15) -> list:
        news_items = []
        for url in self.rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]: # Take top 5 from each feed
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    # Clean html tags from summary roughly
                    summary = summary.split('<')[0]
                    if title:
                        news_items.append(f"{title}. {summary}")
            except Exception as e:
                logger.error(f"Error fetching RSS {url}: {e}")

        return news_items[:limit]

    def analyze_sentiment(self, text_list: list) -> dict:
        """
        Returns average sentiment score from -1 (extreme negative) to 1 (extreme positive)
        """
        if not text_list:
            return {"score": 0.0, "label": "neutral", "summary": "Нет данных"}

        total_score = 0
        for text in text_list:
            sentiment = self.analyzer.polarity_scores(text)
            total_score += sentiment['compound']

        avg_score = total_score / len(text_list)

        if avg_score >= 0.25:
            label = "positive"
        elif avg_score <= -0.25:
            label = "negative"
        else:
            label = "neutral"

        summary = f"Проанализировано {len(text_list)} новостей. Средний score: {avg_score:.2f}."
        return {
            "score": avg_score,
            "label": label,
            "summary": summary,
            "raw_news": text_list
        }

    async def get_macro_calendar(self) -> str:
        """
        Simulates fetching the high-impact macro economic calendar (e.g. CPI, Fed rates).
        In a real scenario, we would parse an API like ForexFactory or Investing.com.
        """
        import datetime
        today = datetime.datetime.utcnow()
        # Simulated logic: Every Wednesday we pretend there's an inflation report
        if today.weekday() == 2:
            return "⚠️ Сегодня выходит важный отчет по инфляции (CPI). Ожидается высокая волатильность."
        elif today.weekday() == 3 and today.day < 8:
            return "⚠️ Сегодня заседание ФРС (Изменение процентной ставки). Рынки в ожидании."
        return "Важных макроэкономических событий сегодня не предвидится."

    async def get_fear_and_greed_index(self) -> str:
        """
        Fetches the Crypto Fear and Greed Index.
        """
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.alternative.me/fng/?limit=1") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        val = data['data'][0]['value']
                        classification = data['data'][0]['value_classification']
                        return f"Индекс Страха и Жадности: {val} ({classification})"
        except Exception as e:
            logger.error(f"Error fetching Fear and Greed: {e}")
        return "Индекс Страха и Жадности: Данные недоступны."

    async def get_social_sentiment(self, symbol: str) -> str:
        """
        Simulates fetching sentiment from Twitter/Reddit/Telegram channels for a specific asset.
        """
        # In MVP, we return a simulated string. In production, this connects to LunarCrush or Twitter API.
        if "BTC" in symbol or "ETH" in symbol:
            return f"Социальные сети: Высокий уровень хайпа вокруг {symbol}. В Telegram каналах преобладает оптимизм (Bullish)."
        elif "SBER" in symbol:
            return f"Социальные сети: {symbol} активно обсуждается в российских инвест-чатах. Ожидание дивидендов."
        return f"Социальные сети: Упоминаний {symbol} сегодня немного (Neutral)."

    def get_global_baseline_sentiment(self) -> dict:
        news = self.fetch_latest_news()
        return self.analyze_sentiment(news)
