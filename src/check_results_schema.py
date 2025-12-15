from src.utils.database import SessionLocal
from sqlalchemy import text
import pandas as pd

db = SessionLocal()
try:
    # Check schema of prediction_results
    query = text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'prediction_results'
    """)
    res = db.execute(query).fetchall()
    for row in res:
        print(f"{row[0]}: {row[1]}")
finally:
    db.close()
