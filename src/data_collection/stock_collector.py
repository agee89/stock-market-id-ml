import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import time
from src.utils.database import SessionLocal, get_db
from src.utils.logger import get_logger
from src.utils.config import get_settings
from src.inference.live_predictor import LivePredictor

logger = get_logger()
settings = get_settings()

class StockCollector:
    def __init__(self, db: Session):
        self.db = db
        # self.symbols = settings.DEFAULT_STOCKS.split(",")
        # User requested NO defaults. Only stocks added via UI should exist.
        self.symbols = []
        self.predictor = LivePredictor(db)

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
                return count
            else:
                logger.warning(f"No data to insert for {symbol}")
                return 0

        except Exception as e:
            logger.error(f"Failed to fetch/save history for {symbol}: {e}")
            self.db.rollback()
        return 0

    def run_daily_update(self):
        """Perform daily closing tasks: Update stock list, 1d history, and final intraday sweep."""
        logger.info("🌅 Running Daily Update Sequence...")
        
        # 1. Update Stock List
        self.update_stock_list_in_db()
        
        # 2. Final Intraday Sweep (Catch 16:00 closes)
        logger.info("🧹 Performing Final Intraday Sweep...")
        self.run_intraday_update(intervals=['15m', '1h'])
        
        # 3. Update Daily Data (1d)
        res = self.db.execute(text("SELECT symbol FROM stocks"))
        all_symbols = [row[0] for row in res.fetchall()]
        
        for symbol in all_symbols:
            try:
                # Fetch 1d history (complete)
                self.fetch_history(symbol, days=365, interval='1d')
                # Predict 1d
                self.predictor.predict_and_save(symbol, '1d')
            except Exception as e:
                logger.error(f"Daily Update Error {symbol}: {e}")
                
        logger.info("✅ Daily Update Sequence Completed.")

    def process_intraday_single(self, symbol, intervals=['15m', '1h']):
        """Helper to process a single symbol for intraday update (Fetch + Predict)."""
        for interval in intervals:
            try:
                # 1m needs less history (max 5 days is OK, but 1 day is faster? kept 5 for safety)
                days = 5 if interval != '1m' else 2 
                c = self.fetch_history(symbol, days=days, interval=interval)
                if c > 0:
                    self.predictor.predict_and_save(symbol, interval)
            except Exception as e:
                logger.error(f"Error {interval} {symbol}: {e}")

    def run_intraday_update(self, intervals=['15m', '1h']):
        """Run quick update for intraday data during market hours."""
        import concurrent.futures

        # Fetch ALL stocks
        try:
            res = self.db.execute(text("SELECT symbol FROM stocks"))
            all_symbols = [row[0] for row in res.fetchall()]
        except:
             all_symbols = self.symbols

        logger.info(f"⚡ Starting Intraday Update {intervals} for {len(all_symbols)} stocks...")
        
        def process_symbol_safe(symbol):
            # Create ISOLATED session for this thread
            thread_db = SessionLocal()
            worker = StockCollector(thread_db)
            try:
                worker.process_intraday_single(symbol, intervals)
            except Exception as e:
                logger.error(f"Thread Safe Wrapper Error {symbol}: {e}")
            finally:
                thread_db.close()

        # Use ThreadPool to speed up
        # max_workers=5 is safe for YFinance to avoid rate limits
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(process_symbol_safe, all_symbols)
                
        logger.info("⚡ Intraday Update Completed.")

if __name__ == "__main__":
    db = SessionLocal()
    collector = StockCollector(db)
    
    logger.info("Starting Stock Collector Service (Smart Mode)...")
    
    # Run once on startup to ensure data
    logger.info("Startup Check...")
    collector.update_stock_list_in_db()
    
    import pytz
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    
    while True:
        try:
            now_wib = datetime.now(jakarta_tz)
            current_hour = now_wib.hour
            current_min = now_wib.minute
            current_day = now_wib.weekday() # 0=Mon, 6=Sun
            
            # Weekend Check
            if current_day >= 5: # Sat, Sun
                 logger.info("Weekend. Sleeping...")
                 time.sleep(3600)
                 continue

            # Daily Update Time (e.g., 17:00 WIB after market close)
            # We check if it's past 17:00 and we haven't run today (logic simplified for loop)
            # Simply: if it is the 17th hour, run daily once then sleep long
            if current_hour == 17:
                logger.info("--- Starting Daily Closing Update ---")
                collector.run_daily_update()
                logger.info("Daily Update Done. Sleeping till tomorrow...")
                time.sleep(10 * 3600) # Sleep 10 hours
                continue
                
            # Intraday Market Hours (09:00 - 16:00 WIB)
            # Logic: Run every minute for 1m data.
            # Run specific logic for 15m/1h updates on :11, :26, :41, :56.
            
            if 8 <= current_hour <= 16:
                # Define 15m trigger minutes (Delayed by 11 mins for safety)
                TRIGGER_15M = [11, 26, 41, 56]
                
                intervals_to_run = ['1m'] # Always run 1m
                
                # Check if we should also run 15m/1h
                if current_min in TRIGGER_15M:
                    intervals_to_run.extend(['15m', '1h'])
                    logger.info(f"🕒 Major Update Cycle: {intervals_to_run}")
                else:
                    logger.info(f"🚀 Turbo Update Cycle (1m only)")

                # Execute
                collector.run_intraday_update(intervals=intervals_to_run)
                
                # Sleep smart until next minute start + 5 seconds
                # This ensures we hit every minute exactly once
                now_check = datetime.now(jakarta_tz)
                sleep_sec = 60 - now_check.second + 5
                logger.info(f"💤 Sleeping {sleep_sec}s until next minute...")
                time.sleep(sleep_sec)
                
            else:
                 # Outside active hours
                 logger.info("Market Closed. Waiting...")
                 time.sleep(3600)

        except Exception as e:
            logger.error(f"Critical Error in Collector Loop: {e}")
            time.sleep(60)
