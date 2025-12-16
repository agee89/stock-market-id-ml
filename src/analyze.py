
import sys
import argparse
from src.analysis.deepseek_analyst import DeepSeekAnalyst
from src.utils.database import SessionLocal
from sqlalchemy import text

def main():
    parser = argparse.ArgumentParser(description="DeepSeek AI Stock Analyst CLI")
    parser.add_argument("symbol", type=str, help="Stock Symbol (e.g., ASII.JK)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    
    # 1. Validate Symbol exists
    db = SessionLocal()
    try:
        res = db.execute(text("SELECT id FROM stocks WHERE symbol = :s"), {"s": symbol}).fetchone()
        if not res:
            print(f"❌ Error: Stock '{symbol}' not found in database.")
            print("   Please add it via the Dashboard first.")
            return
    finally:
        db.close()

    print(f"\n🧠 DeepSeek AI Analyst initialized for {symbol}...")
    print("   (Analysing Daily, H1, and 15m data context...)")
    print("   Please wait 10-20 seconds...\n")

    # 2. Run Analysis
    try:
        analyst = DeepSeekAnalyst()
        result = analyst.analyze_stock(symbol)
        
        if result:
            print("="*60)
            print(f"📊 ANALYSIS REPORT: {symbol}")
            print("="*60)
            print(result)
            print("="*60)
        else:
            print("❌ No result returned. Check logs.")

    except Exception as e:
        print(f"❌ Analysis Failed: {e}")

if __name__ == "__main__":
    main()
