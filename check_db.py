from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    symbol = "BBRI.JK"
    interval = "15m"
    query = text("""
        SELECT timestamp, interval, close 
        FROM stock_prices p
        JOIN stocks s ON s.id = p.stock_id
        WHERE s.symbol = :symbol AND p.interval = :interval
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    res = db.execute(query, {"symbol": symbol, "interval": interval}).fetchall()
    print(f"Latest 5 rows for {symbol} ({interval}):")
    for row in res:
        print(row)
except Exception as e:
    print(e)
finally:
    db.close()
