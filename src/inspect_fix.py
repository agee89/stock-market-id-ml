from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    # Check pending results (is_correct is NULL)
    query = text("""
        SELECT pr.id, pr.prediction_id, pr.actual_price, pr.is_correct, 
               p.target_date, p.interval, s.symbol
        FROM prediction_results pr
        JOIN predictions p ON p.id = pr.prediction_id
        JOIN stocks s ON s.id = p.stock_id
        WHERE pr.is_correct IS NULL
        AND p.target_date >= CURRENT_DATE - INTERVAL '3 day'
        ORDER BY p.target_date DESC
    """)
    res = db.execute(query).fetchall()
    if res:
        df = pd.DataFrame(res, columns=['id', 'pred_id', 'actual', 'is_correct', 'target', 'interval', 'symbol'])
        print(df)
    else:
        print("No pending results found in prediction_results.")
        
    # Check "orphaned" predictions (Prediction exists but NO Result entry at all)
    query_orphaned = text("""
        SELECT p.id, p.target_date, p.interval, s.symbol
        FROM predictions p
        JOIN stocks s ON s.id = p.stock_id
        LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
        WHERE pr.id IS NULL
        AND p.target_date <= NOW()  -- Should have result by now
        AND p.target_date >= CURRENT_DATE - INTERVAL '3 day'
        ORDER BY p.target_date DESC
    """)
    res_orph = db.execute(query_orphaned).fetchall()
    if res_orph:
         print("\nOrphaned Predictions (Missing Result Row):")
         df_o = pd.DataFrame(res_orph, columns=['id', 'target', 'interval', 'symbol'])
         print(df_o)
         
finally:
    db.close()
