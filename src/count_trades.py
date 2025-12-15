from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    print("Analyzing Daily Valid Trades (PnL != 0)...")
    
    # Query: Count trades where actual_change_pct IS NOT ZERO and within last 5 days
    query = text("""
        SELECT 
            DATE(p.prediction_date) as trade_date,
            COUNT(*) as total_signals,
            SUM(CASE WHEN pr.actual_change_pct != 0 THEN 1 ELSE 0 END) as valid_trades,
            SUM(CASE WHEN pr.is_correct = true THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN pr.actual_change_pct != 0 THEN pr.actual_change_pct ELSE NULL END), 2) as avg_pnl
        FROM predictions p
        JOIN prediction_results pr ON pr.prediction_id = p.id
        WHERE p.prediction_date >= CURRENT_DATE - INTERVAL '5 days'
        GROUP BY DATE(p.prediction_date)
        ORDER BY trade_date DESC
    """)
    
    res = db.execute(query).fetchall()
    
    if res:
        df = pd.DataFrame(res, columns=['Date', 'Total Signals', 'Valid Trades (Active)', 'Wins', 'Avg PnL %'])
        print(df.to_string(index=False))
    else:
        print("No trades found in the last 5 days.")
        
finally:
    db.close()
