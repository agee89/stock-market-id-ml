import os
import sys
from sqlalchemy import text
from src.utils.database import SessionLocal

def fix_results():
    db = SessionLocal()
    try:
        print("⚠️  FLUSHING ALL PREDICTION RESULTS (Due to Date Bug Fix)...")
        
        # 1. Count
        count = db.execute(text("SELECT COUNT(*) FROM prediction_results")).scalar()
        print(f"Deleting {count} records...")
        
        # 2. Delete All
        db.execute(text("DELETE FROM prediction_results"))
        db.commit()
        print("✅ Flushed. All history will now be re-verified with CORRECT timestamps.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_results()
