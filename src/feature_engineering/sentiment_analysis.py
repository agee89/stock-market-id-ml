from textblob import TextBlob
from sqlalchemy.orm import Session
from src.utils.logger import get_logger

logger = get_logger()

class SentimentAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def analyze_text(self, text: str) -> dict:
        """
        Analyze sentiment of a text string.
        Returns dict with polarity and subjectivity.
        """
        try:
            if not text:
                return {"polarity": 0.0, "subjectivity": 0.0}
            
            blob = TextBlob(text)
            return {
                "polarity": blob.sentiment.polarity,
                "subjectivity": blob.sentiment.subjectivity
            }
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {"polarity": 0.0, "subjectivity": 0.0}

    # Future: Add method to process news news_sentiment table
