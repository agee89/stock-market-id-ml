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
        """Keyword-based sentiment (Indonesian + English)."""
        text_lower = text_content.lower()
        
        # Expanded Keyword List
        positive_words = [
            # ID
            'naik', 'menguat', 'untung', 'laba', 'dividen', 'bullish', 'hijau', 'positif', 
            'terbang', 'rekor', 'akumulasi', 'buy', 'loncat', 'meroket',
            # EN
            'up', 'rise', 'gain', 'profit', 'dividend', 'green', 'positive', 
            'soar', 'record', 'accumulate', 'strong', 'growth'
        ]
        negative_words = [
            # ID
            'turun', 'melemah', 'rugi', 'anjlok', 'bearish', 'merah', 'negatif', 
            'koreksi', 'jual', 'sell', 'cut loss', 'longsor', 'suspend',
            # EN
            'down', 'fall', 'loss', 'plunge', 'red', 'negative', 
            'correction', 'drop', 'weak', 'crash', 'suspension'
        ]
        
        score = 0
        
        for word in positive_words:
            if word in text_lower:
                score += 0.5
                
        for word in negative_words:
            if word in text_lower:
                score -= 0.5
                
        # Clamp between -1 and 1
        return max(min(score, 1.0), -1.0)

    def fetch_news(self, query: str = "Saham", stock_id: int = None, symbol: str = None):
        """Fetch news from Yahoo Finance + Google News Fallback."""
        import yfinance as yf
        
        articles = []
        
        # 1. Yahoo Finance (Direct Ticker News)
        if symbol:
            try:
                logger.info(f"Fetching Yahoo Finance News for {symbol}")
                yf_news = yf.Ticker(symbol).news
                if yf_news:
                    for item in yf_news:
                        # Converting unix ts
                        pub_ts = item.get('providerPublishTime', time.time())
                        pub_date = datetime.fromtimestamp(pub_ts)
                        
                        articles.append({
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'source': item.get('publisher', 'Yahoo Finance'),
                            'date': pub_date
                        })
            except Exception as e:
                logger.warning(f"Yahoo News failed for {symbol}: {e}")

        # 2. Google News Fallback (if Yahoo yielded < 2 articles)
        if len(articles) < 2:
            try:
                # Construct RSS URL for Indonesia (id-ID)
                # Clean the query
                clean_query = query.replace(".JK", "").replace("Indonesia Stock", "").strip()
                encoded_query = urllib.parse.quote_plus(f"saham {clean_query}")
                rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id-ID&gl=ID&ceid=ID:id"
                
                logger.info(f"Fetching Google News RSS for: {clean_query}")
                feed = feedparser.parse(rss_url)
                
                for entry in feed.entries[:5]:
                    if hasattr(entry, 'published_parsed'):
                         pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    else:
                         pub_date = datetime.now()
                    
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'source': entry.source.title if hasattr(entry, 'source') else "Google News",
                        'date': pub_date
                    })
            except Exception as e:
                logger.error(f"Google News failed: {e}")

        # Process & Save
        count = 0
        
        # AI BATCH ANALYSIS
        if articles:
            try:
                # 3. Analyze Batch with DeepSeek (Dedicated News Analyst)
                from src.analysis.news_analyst import DeepSeekNewsAnalyst
                analyst = DeepSeekNewsAnalyst()
                
                headlines = [a['title'] for a in articles]
                # Get single score for the whole batch
                if not headlines: return
                
                logger.info(f"🧠 AI Analyzing {len(headlines)} headlines for {symbol}...")
                ai_sentiment_score = analyst.analyze_batch(headlines)
                ai_sentiment_label = "POSITIVE" if ai_sentiment_score > 0 else "NEGATIVE" if ai_sentiment_score < 0 else "NEUTRAL"
                
                logger.info(f"🧠 AI Score: {ai_sentiment_score} ({ai_sentiment_label})")

                # Assign this AI score to ALL headlines in this batch for simplicity in ML (Contextual)
                # Or we could just store it as the latest sentiment.
                # For now, we save individual records but with the Batch Score 
                # (Assuming the news event drives the batch sentiment)
                
                for art in articles:
                    try:
                        title = art['title']
                        date_str = art['date'].strftime('%Y-%m-%d')

                        sql = text("""
                            INSERT INTO news_sentiment (stock_id, date, title, content, source, url, sentiment_score, sentiment_label)
                            VALUES (:stock_id, :date, :title, :content, :source, :url, :score, :label)
                            ON CONFLICT DO UPDATE SET sentiment_score = :score, sentiment_label = :label
                        """)
                        
                        self.db.execute(sql, {
                            "stock_id": stock_id,
                            "date": date_str,
                            "title": title,
                            "content": title, 
                            "source": art['source'],
                            "url": art['link'],
                            "score": ai_sentiment_score, # AI Score
                            "label": ai_sentiment_label
                        })
                        count += 1
                    except Exception as e:
                        continue
                
                self.db.commit()
                logger.info(f"Saved {count} articles with AI Score {ai_sentiment_score}")
                
            except Exception as e:
                logger.error(f"AI Sentiment Failed: {e}")
        else:
             logger.warning(f"No articles found for {symbol}")

if __name__ == "__main__":
    pass
