import sys
import time
from sqlalchemy import text
from src.utils.database import SessionLocal
from src.inference.live_predictor import LivePredictor
from src.utils.logger import get_logger

# Configure logger to output to stdout just in case
logger = get_logger()

def verify_all_now():
    db = SessionLocal()
    predictor = LivePredictor(db)
    
    try:
        print("🚀 Starting Immediate Verification...")
        
        # 1. Get all stocks
        stocks = db.execute(text("SELECT id, symbol FROM stocks")).fetchall()
        print(f"Found {len(stocks)} stocks to check.")
        
        intervals = ['15m', '1h', '1d']
        total_verified = 0
        
        for stock_id, symbol in stocks:
            for interval in intervals:
                # Loop until no more pending for this symbol/interval
                # Since evaluating 50 at a time.
                while True:
                    # We can hack this: check pending count first?
                    # Or modify evaluate_past_predictions to return count.
                    # Since I cannot easily modify signature without reloading, 
                    # I will rely on the fact that if it finds nothing, it returns quickly.
                    # Wait, checking pending count is safer to avoid infinite loop if bug exists.
                    
                    q_pending = text("""
                        SELECT COUNT(*)
                        FROM predictions p
                        LEFT JOIN prediction_results pr ON p.id = pr.prediction_id
                        WHERE p.stock_id = :sid 
                        AND p.target_date < NOW() 
                        AND pr.id IS NULL
                    """)
                    count = db.execute(q_pending, {"sid": stock_id}).scalar()
                    
                    if count == 0:
                        break
                        
                    print(f"Processing {symbol} [{interval}] - Pending: {count}...")
                    
                    try:
                        predictor.evaluate_past_predictions(stock_id, symbol, interval)
                        total_verified += 50 # approximate
                    except Exception as e:
                        print(f"Error on {symbol}: {e}")
                        break
                    
                    # Small sleep to yield DB
                    time.sleep(0.1)
        
        print(f"✅ Immediate Verification Complete. Processed ~{total_verified} records.")
        
    except Exception as e:
        print(f"❌ Script failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_all_now()
