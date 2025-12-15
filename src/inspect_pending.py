from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    # Check pending predictions for today
    query = text("""
        SELECT p.id, s.symbol, p.interval, p.timestamp, p.predicted_price, p.actual_price, p.is_win
        FROM predictions p
        JOIN stocks s ON s.id = p.stock_id
        WHERE p.is_win IS NULL
        AND p.timestamp >= CURRENT_DATE - INTERVAL '1 day'
        ORDER BY p.timestamp DESC
    """)
    res = db.execute(query).fetchall()
    df = pd.DataFrame(res, columns=['id', 'symbol', 'interval', 'timestamp', 'predicted', 'actual', 'is_win'])
    print(df)
finally:
    db.close()
