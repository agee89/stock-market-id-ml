import feedparser
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.utils.logger import get_logger
from src.utils.config import get_settings
from datetime import datetime
import time
import urllib.parse

logger = get_logger()
settings = get_settings()

class NewsCollector:
    def __init__(self, db: Session):
        self.db = db
        # We don't need API Key for Google RSS
    
    def calculate_sentiment_id(self, text_content: str) -> float:
        """Simple keyword-based sentiment for Indonesian finance news."""
        text_lower = text_content.lower()
        
        positive_words = ['naik', 'menguat', 'untung', 'laba', 'dividen', 'bullish', 'hijau', 'positif', 'terbang', 'rekor', 'akumulasi', 'buy']
        negative_words = ['turun', 'melemah', 'rugi', 'anjlok', 'bearish', 'merah', 'negatif', 'koreksi', 'jual', 'sell', 'cut loss']
        
        score = 0
        
        for word in positive_words:
            if word in text_lower:
                score += 0.5
                
        for word in negative_words:
            if word in text_lower:
                score -= 0.5
                
        # Clamp between -1 and 1
        return max(min(score, 1.0), -1.0)

    def fetch_news(self, query: str = "Saham", stock_id: int = None):
        """Fetch news from Google News RSS (Indonesia)."""
        # Enhance query for local context if it looks like a symbol
        # e.g. "BBCA.JK" -> "Saham BBCA Bank Central Asia"
        # query might be "BBCA.JK Indonesia Stock"
        
        # Clean the query
        clean_query = query.replace(".JK", "").replace("Indonesia Stock", "").strip()
        
        # URL Encode
        encoded_query = urllib.parse.quote_plus(f"saham {clean_query}")
        
        # Construct RSS URL for Indonesia (id-ID)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id-ID&gl=ID&ceid=ID:id"
        
        logger.info(f"Fetching Google News RSS for: {clean_query}")
        
        try:
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                logger.warning(f"No articles found for {search_query}")
                return

            logger.info(f"Found {len(feed.entries)} articles")
            
            count = 0
            for entry in feed.entries[:10]: # Limit to top 10 recent
                try:
                    # Parse date (RSS usually has 'published_parsed' struct_time)
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    else:
                        pub_date = datetime.now()
                        
                    date_str = pub_date.strftime('%Y-%m-%d')
                    
                    title = entry.title
                    link = entry.link
                    source = entry.source.title if hasattr(entry, 'source') else "Google News"
                    
                    # Calculate Sentiment (Indonesian)
                    sentiment_score = self.calculate_sentiment_id(title)
                    sentiment_label = "POSITIVE" if sentiment_score > 0 else "NEGATIVE" if sentiment_score < 0 else "NEUTRAL"
                    
                    # Save to DB
                    sql = text("""
                        INSERT INTO news_sentiment (stock_id, date, title, content, source, url, sentiment_score, sentiment_label)
                        VALUES (:stock_id, :date, :title, :content, :source, :url, :score, :label)
                        ON CONFLICT DO NOTHING
                    """)
                    
                    # Note: We don't have a unique constraint on news URL/Title in schema yet,
                    # so duplicates might pile up. Ideally we should have one.
                    # For now, let's just insert.
                    
                    self.db.execute(sql, {
                        "stock_id": stock_id,
                        "date": date_str,
                        "title": title,
                        "content": title, # RSS often has no description, use title
                        "source": source,
                        "url": link,
                        "score": sentiment_score,
                        "label": sentiment_label
                    })
                    count += 1
                except Exception as e:
                    continue
            
            self.db.commit()
            logger.info(f"Saved {count} new articles from Google News")
            
        except Exception as e:
            logger.error(f"Error fetching Google News: {e}")

if __name__ == "__main__":
    pass
