from src.utils.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Check predictions created in the last hour
    query = text("""
        SELECT count(*) FROM predictions 
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)
    count = db.execute(query).fetchone()[0]
    print(f"Fresh Predictions (Last 1h): {count}")

    # Show some samples
    query_samples = text("""
        SELECT s.symbol, p.interval, p.predicted_direction, p.predicted_price, p.created_at
        FROM predictions p
        JOIN stocks s ON p.stock_id = s.id
        WHERE p.created_at > NOW() - INTERVAL '1 hour'
        ORDER BY p.created_at DESC
        LIMIT 10
    """)
    samples = db.execute(query_samples).fetchall()
    for row in samples:
        print(f"{row[0]} [{row[1]}] -> {row[2]} @ {row[3]} ({row[4]})")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
