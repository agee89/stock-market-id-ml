from src.utils.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("Deleting orphaned predictions (no result row and past target date)...")
    
    # 1. Select for verification
    query_chk = text("""
        SELECT p.id, p.target_date, p.interval
        FROM predictions p
        LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
        WHERE pr.id IS NULL
        AND p.target_date <= NOW()
    """)
    res = db.execute(query_chk).fetchall()
    print(f"Found {len(res)} stuck predictions.")
    
    # 2. Delete them
    if res:
        query_del = text("""
            DELETE FROM predictions p
            WHERE p.id IN (
                SELECT p.id
                FROM predictions p
                LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
                WHERE pr.id IS NULL
                AND p.target_date <= NOW()
            )
        """)
        db.execute(query_del)
        db.commit()
        print("Deleted stuck predictions.")
        
    print("Done.")
finally:
    db.close()
