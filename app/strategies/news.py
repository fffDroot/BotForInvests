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
            "https://www.cnbc.com/id/100003114/device/rss/rss.html" # CNBC Top News
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

    def get_global_baseline_sentiment(self) -> dict:
        news = self.fetch_latest_news()
        return self.analyze_sentiment(news)
