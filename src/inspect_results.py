from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    # Check pending results
    query = text("""
        SELECT pr.id, pr.prediction_id, pr.actual_price, pr.is_win, 
               p.target_date, p.interval, s.symbol
        FROM prediction_results pr
        JOIN predictions p ON p.id = pr.prediction_id
        JOIN stocks s ON s.id = p.stock_id
        WHERE pr.is_win IS NULL
        AND p.target_date >= CURRENT_DATE - INTERVAL '2 day'
        ORDER BY p.target_date DESC
    """)
    res = db.execute(query).fetchall()
    if res:
        df = pd.DataFrame(res, columns=['id', 'pred_id', 'actual', 'is_win', 'target', 'interval', 'symbol'])
        print(df)
    else:
        print("No pending results found in prediction_results.")

    # Also check predictions WITHOUT results
    query_missing = text("""
        SELECT p.id, p.target_date, p.interval, s.symbol
        FROM predictions p
        JOIN stocks s ON s.id = p.stock_id
        LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
        WHERE pr.id IS NULL
        AND p.target_date >= CURRENT_DATE - INTERVAL '1 day'
    """)
    res_missing = db.execute(query_missing).fetchall()
    if res_missing:
        print("\nPredictions missing from results table:")
        df_m = pd.DataFrame(res_missing, columns=['id', 'target', 'interval', 'symbol'])
        print(df_m)
        
finally:
    db.close()
