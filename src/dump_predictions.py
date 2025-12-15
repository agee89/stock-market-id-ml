from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    # List recent predictions regardless of status
    query = text("""
        SELECT p.id, s.symbol, p.interval, p.prediction_date, p.target_date, 
               pr.is_correct, pr.actual_price
        FROM predictions p
        JOIN stocks s ON s.id = p.stock_id
        LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
        WHERE s.symbol = 'ASII.JK' OR s.symbol = 'BBCA.JK'  -- Just examples or leave generic
        LIMIT 20
    """)
    # Or just generic
    query_gen = text("""
        SELECT p.id, s.symbol, p.interval, p.prediction_date, p.target_date, 
               pr.is_correct, pr.actual_price
        FROM predictions p
        JOIN stocks s ON s.id = p.stock_id
        LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
        ORDER BY p.prediction_date DESC
        LIMIT 20
    """)
    
    res = db.execute(query_gen).fetchall()
    df = pd.DataFrame(res, columns=['id', 'symbol', 'interval', 'pred_date', 'target_date', 'is_correct', 'actual_price'])
    print(df)

finally:
    db.close()
