from src.utils.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # List tables
    query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    res = db.execute(query).fetchall()
    print("Tables:", [row[0] for row in res])
    
    # Check trade_history or signals
    query = text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'signals' OR table_name = 'predictions'
        ORDER BY table_name, ordinal_position
    """)
    res = db.execute(query).fetchall()
    for row in res:
        print(f"{row[0]}")
finally:
    db.close()
