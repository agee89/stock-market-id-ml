import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import time
from src.utils.database import SessionLocal, get_db
from src.utils.logger import get_logger
from src.utils.config import get_settings

logger = get_logger()
settings = get_settings()

class StockCollector:
    def __init__(self, db: Session):
        self.db = db
        self.symbols = settings.DEFAULT_STOCKS.split(",")

    def update_stock_list_in_db(self):
        """Ensure all default stocks exist in the database."""
        for symbol in self.symbols:
            try:
                # Basic check if stock exists
                result = self.db.execute(
                    text("SELECT id FROM stocks WHERE symbol = :symbol"),
                    {"symbol": symbol}
                ).fetchone()

                if not result:
                    logger.info(f"Adding new stock to DB: {symbol}")
                    # Fetch info if possible, or just insert symbol
                    ticker = yf.Ticker(symbol)
                    info = ticker.info or {} # Handle None
                    name = info.get('longName', symbol)
                    sector = info.get('sector', 'Unknown')
                    
                    self.db.execute(
                        text("INSERT INTO stocks (symbol, name, sector) VALUES (:symbol, :name, :sector)"),
                        {"symbol": symbol, "name": name, "sector": sector}
                    )
                    self.db.commit()
            except Exception as e:
                logger.error(f"Error updating stock list for {symbol}: {e}")
                self.db.rollback()

    def fetch_history(self, symbol: str, days: int = 365, interval: str = '1d'):
        """Fetch historical data for a stock."""
        try:
            logger.info(f"Fetching {days} days of history for {symbol} with interval {interval}")
            
            # Simple logic: for intraday (interval < 1d), yfinance limits history.
            # 1m = max 7 days
            # 5m = max 60 days
            # 15m = max 60 days
            # 1h = max 730 days
            
            # Determine Period or Start Date
            # For 1d data, we prefer 'start' argument for precision (e.g. 10 years)
            if interval == '1d':
                 start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                 ticker = yf.Ticker(symbol)
                 df = ticker.history(start=start_date, interval=interval)
            else:
                period = f"{days}d"
                if interval == '1m':
                    period = "7d" # Max allowed
                elif interval in ['5m', '15m']:
                    period = "60d" # Max allowed
                elif interval == '1h':
                    period = "730d" # Max allowed
                
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return

            # Get stock_id
            stock_id = self.db.execute(
                text("SELECT id FROM stocks WHERE symbol = :symbol"),
                {"symbol": symbol}
            ).fetchone()[0]

            # Also fetch news while we are at it (only if daily to avoid spam)
            if interval == '1d':
                try:
                    from src.data_collection.news_collector import NewsCollector
                    news_collector = NewsCollector(self.db)
                    news_collector.fetch_news(query=f"{symbol} Indonesia Stock", stock_id=stock_id)
                except Exception as e:
                    logger.error(f"News collection failed: {e}")

            insert_data = []
            count = 0
            for index, row in df.iterrows():
                try:
                    # Index is already datetime/timestamp
                    ts = index.to_pydatetime()
                    # Ensure timezone naive or UTC? Postgres timestamp is naive.
                    # yfinance returns timezone aware. Convert to naive (local time) or UTC.
                    if ts.tzinfo is not None:
                        ts = ts.astimezone().replace(tzinfo=None) # Local time naive
                    
                    # Normalize timestamp for 1d data to avoid 01:00, 17:00 duplicates
                    if interval == '1d':
                        ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    insert_data.append({
                        "stock_id": stock_id,
                        "timestamp": ts,
                        "interval": interval,
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": int(row['Volume']),
                        "adj_close": float(row['Adj Close']) if 'Adj Close' in row else float(row['Close'])
                    })
                    count += 1
                except Exception as e:
                    logger.error(f"Error processing row {index} for {symbol}: {e}")
            
            if insert_data:
                # Perform bulk insert
                self.db.execute(
                    text("""
                        INSERT INTO stock_prices (stock_id, timestamp, interval, open, high, low, close, volume, adj_close)
                        VALUES (:stock_id, :timestamp, :interval, :open, :high, :low, :close, :volume, :adj_close)
                        ON CONFLICT (stock_id, timestamp, interval) DO UPDATE 
                        SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume, adj_close=EXCLUDED.adj_close
                    """),
                    insert_data
                )
                self.db.commit()
                logger.info(f"Successfully updated {count} {interval} records for {symbol}")
            else:
                logger.warning(f"No data to insert for {symbol}")

        except Exception as e:
            logger.error(f"Failed to fetch/save history for {symbol}: {e}")
            self.db.rollback()

    def run_daily_update(self):
        """Run daily update for all stocks in the Database."""
        # 1. Seed: Ensure default stocks from .env are in DB
        self.update_stock_list_in_db()
        
        # 2. Fetch ALL stocks from DB (Source of Truth) to include dynamically added ones
        try:
            res = self.db.execute(text("SELECT symbol FROM stocks"))
            all_symbols = [row[0] for row in res.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch stock list from DB: {e}")
            all_symbols = self.symbols # Fallback to env list
            
        logger.info(f"Starting Daily Update for {len(all_symbols)} stocks: {all_symbols}")

        for symbol in all_symbols:
            logger.info(f"Processing {symbol}...")
            self.fetch_history(symbol, days=settings.LOOKBACK_DAYS)
            time.sleep(1) # Be nice to API

if __name__ == "__main__":
    db = SessionLocal()
    collector = StockCollector(db)
    
    logger.info("Starting Stock Collector Service (Continuous Mode)...")
    
    while True:
        try:
            logger.info("--- Starting Daily Update Cycle ---")
            collector.run_daily_update()
            logger.info("--- Cycle Completed. Sleeping for 12 Hours... ---")
        except Exception as e:
            logger.error(f"Critical Error in Collector Loop: {e}")
        
        # Sleep for 12 hours (43200 seconds)
        time.sleep(43200)
