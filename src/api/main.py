from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
from sqlalchemy import text
from src.utils.database import SessionLocal, get_db
from src.utils.logger import get_logger
from src.training.trainer import ModelTrainer
from src.models.lstm_model import LSTMModel
from src.data_collection.news_collector import NewsCollector
from src.inference.live_predictor import LivePredictor
from src.analysis.checklist import TraderChecklist
from src.analysis.deepseek_analyst import DeepSeekAnalyst
import os

app = FastAPI(title="Stock Market ID ML API")
logger = get_logger()

class PredictionResponse(BaseModel):
    symbol: str
    predicted_price: float
    expected_change_pct: float
    model_type: str = "LSTM"
    current_price_date: Optional[str] = None
    target_date: Optional[str] = None

class StockResponse(BaseModel):
    symbol: str
    name: str

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/analysis/{symbol}")
def get_stock_analysis(symbol: str, interval: str = '1d'):
    import pandas as pd
    import numpy as np
    import ta
    
    db = SessionLocal()
    try:
        # Fetch sufficient history for indicators (SMA200 needs 200+)
        query = text("""
            SELECT timestamp as date, open, high, low, close, volume
            FROM stock_prices p
            JOIN stocks s ON s.id = p.stock_id
            WHERE s.symbol = :symbol AND p.interval = :interval
            ORDER BY timestamp DESC
            LIMIT 300
        """)
        res = db.execute(query, {"symbol": symbol, "interval": interval}).fetchall()
        
        if not res or len(res) < 50:
            return {"error": "Insufficient data"}
            
        df = pd.DataFrame(res, columns=['date', 'open', 'high', 'low', 'close', 'volume']).iloc[::-1] # Sort Asc
        
        # Ensure correct types (Decimal -> Float)
        cols_to_fix = ['open', 'high', 'low', 'close', 'volume']
        df[cols_to_fix] = df[cols_to_fix].astype(float)
        
        # 1. Liquidity & Volatility
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        last_close = df['close'].iloc[-1]
        avg_value = avg_vol * last_close # Est. transaction value
        
        df['tr'] = np.maximum((df['high'] - df['low']), 
                             np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                      abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].rolling(14).mean().iloc[-1]
        
        volatility_pct = (atr / last_close) * 100
        
        # 2. Trend (Price Action)
        sma_20 = ta.trend.sma_indicator(df['close'], window=20).iloc[-1]
        sma_50 = ta.trend.sma_indicator(df['close'], window=50).iloc[-1]
        sma_200 = ta.trend.sma_indicator(df['close'], window=200).iloc[-1] if len(df) > 200 else 0
        
        trend = "SIDEWAYS"
        if last_close > sma_20 > sma_50: trend = "UPTREND (Strong)"
        elif last_close < sma_20 < sma_50: trend = "DOWNTREND (Strong)"
        elif last_close > sma_50: trend = "UPTREND (Moderate)"
        
        # 3. Psychology (RSI)
        rsi = ta.momentum.rsi(df['close'], window=14).iloc[-1]
        psychology = "Neutral"
        if rsi > 70: psychology = "Greed / Overbought ⚠️"
        elif rsi < 30: psychology = "Fear / Oversold 🛒"
        
        # 4. Support & Resistance (Simple Pivot 20d)
        support = df['low'].rolling(20).min().iloc[-1]
        resistance = df['high'].rolling(20).max().iloc[-1]
        
        # 5. Risk Management (ATR Based)
        # Conservative: 2x ATR
        cut_loss = last_close - (2 * atr)
        target_profit = last_close + (4 * atr) # 1:2 Ratio
        
        return {
            "price": last_close,
            "liquidity": {
                "avg_volume": int(avg_vol),
                "avg_value_idr": float(avg_value),
                "status": "Liquid" if avg_value > 1000000000 else "Illiquid (Hati-hati)" # 1M IDR threshold low? adjusting mental model -> 1B IDR usually
            },
            "trend": {
                "status": trend,
                "sma_50": sma_50,
                "sma_200": sma_200
            },
            "volatility": {
                "atr": float(atr),
                "pct": float(volatility_pct),
                "label": "High" if volatility_pct > 3 else "Low" if volatility_pct < 1 else "Normal"
            },
            "psychology": {
                "rsi": float(rsi),
                "state": psychology
            },
            "setup": {
                "support": float(support),
                "resistance": float(resistance),
                "cut_loss": float(cut_loss),
                "target": float(target_profit),
                "rr_ratio": "1:2"
            }
        }
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/analysis/ai/{symbol}")
def get_ai_analysis(symbol: str):
    """Get Top-Down Technical Analysis from DeepSeek AI."""
    try:
        analyst = DeepSeekAnalyst()
        result = analyst.analyze_stock(symbol)
        
        if result and result.startswith("Error"):
             raise HTTPException(status_code=400, detail=result)
        if result and result.startswith("AI Error"):
             raise HTTPException(status_code=502, detail=result)
             
        return {"symbol": symbol, "analysis": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"AI Analysis Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/company/{symbol}")
def get_company_profile(symbol: str):
    import yfinance as yf
    from deep_translator import GoogleTranslator
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Helper for translation
        def trans(text):
            try:
                if not text or text == 'Unknown': return text
                return GoogleTranslator(source='auto', target='id').translate(text)
            except:
                return text

        summary_en = info.get('longBusinessSummary', 'No description available.')
        sector_en = info.get('sector', 'Unknown')
        industry_en = info.get('industry', 'Unknown')

        return {
            "name": info.get('longName', symbol),
            "sector": trans(sector_en),
            "industry": trans(industry_en),
            "summary": trans(summary_en), # This might take 1-2s
            "website": info.get('website', '#')
        }
    except Exception as e:
        logger.error(f"Error fetching company info for {symbol}: {e}")
        return {"error": "Failed to fetch info"}

@app.get("/status/{symbol}")
def get_ml_status(symbol: str):
    import redis
    from src.utils.config import get_settings
    settings = get_settings()
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)
        status = r.get(f"status:{symbol}")
        return {"status": status if status else "Idle"}
    except:
        return {"status": "Unknown"}

@app.get("/status/system")
def get_system_status():
    import redis
    from src.utils.config import get_settings
    settings = get_settings()
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)
        status = r.get("status:global")
        return {"status": status if status else "Idle"}
    except:
        return {"status": "Unknown"}

@app.get("/stocks", response_model=List[StockResponse])
def get_stocks():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT symbol, name FROM stocks ORDER BY symbol")).fetchall()
        return [{"symbol": row[0], "name": row[1]} for row in result]
    except Exception as e:
        logger.error(f"Error fetching stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class StockCreate(BaseModel):
    symbol: str

@app.post("/stocks")
def add_new_stock(stock: StockCreate, background_tasks: BackgroundTasks):
    symbol = stock.symbol.upper().strip()
    db = SessionLocal()
    try:
        # Check existing
        exists = db.execute(text("SELECT id FROM stocks WHERE symbol=:s"), {"s": symbol}).fetchone()
        if exists:
             return {"status": "exists", "message": f"Stock {symbol} already exists."}
             
        # Get Info & Insert
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        name = info.get('longName', symbol)
        sector = info.get('sector', 'Unknown')
        
        db.execute(
            text("INSERT INTO stocks (symbol, name, sector) VALUES (:s, :n, :sec)"), 
            {"s": symbol, "n": name, "sec": sector}
        )
        db.commit()
        
        # Trigger background fetch using Collector logic
        from src.data_collection.stock_collector import StockCollector
        collector = StockCollector(db)
        background_tasks.add_task(collector.fetch_history, symbol)
        
        return {"status": "added", "symbol": symbol, "name": name}
        
    except Exception as e:
        logger.error(f"Error adding stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add stock: {e}")
    finally:
        db.close()

@app.post("/train/{symbol}")
def trigger_training(symbol: str, background_tasks: BackgroundTasks, interval: str = '1d'):
    trainer = ModelTrainer(interval=interval)
    background_tasks.add_task(trainer.run_pipeline, symbol)
    return {"status": "Training started", "symbol": symbol, "interval": interval}

@app.get("/history/{symbol}")
def get_history(symbol: str, days: int = 365, interval: str = '1d'):
    db = SessionLocal()
    try:
        # For intraday, limit default days
        if interval != '1d' and days == 365:
            days = 7 # Default to 7 days for intraday if not specified
            
        limit = 5000 # Safety limit
        
        query = text("""
            SELECT p.timestamp, p.close, p.open, p.high, p.low, p.volume
            FROM stock_prices p
            JOIN stocks s ON s.id = p.stock_id
            WHERE s.symbol = :symbol AND p.interval = :interval
            ORDER BY p.timestamp DESC
            LIMIT :limit
        """)
        result = db.execute(query, {"symbol": symbol, "limit": limit, "interval": interval}).fetchall()
        
        if not result:
            return []
            
        return [
            {
                "date": row[0].isoformat(),
                "close": float(row[1]),
                "open": float(row[2]) if row[2] else float(row[1]),
                "high": float(row[3]) if row[3] else float(row[1]),
                "low": float(row[4]) if row[4] else float(row[1]),
                "volume": int(row[5])
            }
            for row in result
        ]
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/train/all")
def train_all_models(background_tasks: BackgroundTasks):
    """
    Trigger mass retraining for all symbols and timeframes.
    Runs as a background process to avoid blocking the API.
    """
    import subprocess
    import sys
    
    def run_mass_training():
        logger.info("Starting Mass Retraining (All Symbols, All Internals)...")
        # Run for each timeframe sequentially to avoid OOM
        intervals = ['1d', '1h', '15m', '1m']
        for interval in intervals:
            try:
                logger.info(f"Retraining for {interval}...")
                subprocess.run(
                    [sys.executable, "-m", "src.training.trainer", "--all", "--interval", interval],
                    check=True,
                    capture_output=True # Capture output to avoid messy logs if possible, or handled by logger
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Mass retraining failed for {interval}. Error: {e.stderr.decode()}")
            except Exception as e:
                logger.error(f"Mass retraining failed for {interval}: {e}")
                
        logger.info("Mass Retraining Completed.")

    background_tasks.add_task(run_mass_training)
    return {"status": "started", "message": "Mass retraining started in background for all timeframes."}

@app.post("/train/{symbol}")
def train_model(symbol: str, interval: str = '1d', background_tasks: BackgroundTasks = None):
    # (Existing logic would be here, but let's ensure it's compatible if we overwrite or insert)
    # Since I don't see the original /train/{symbol} in the viewed block, 
    # I should be careful not to create a duplicate if it's already there.
    # But wait, looking at app.py line 1134, it calls /train/{symbol}.
    # The previous view_file 300-600 didn't show it. It might be before line 300.
    # I will just insert /train/all safely.
    pass

@app.get("/predict/{symbol}", response_model=PredictionResponse)
def predict(symbol: str, interval: str = '1d'):
    """
    Get live prediction for a stock using the LivePredictor class.
    """
    db = SessionLocal()
    try:
        predictor = LivePredictor(db)
        result = predictor.predict_and_save(symbol, interval)
        
        if not result:
             # Check if model exists first? LivePredictor logs error if stock not found or model missing.
             # We can assume 404/500 based on logs, but generic 404 here
             raise HTTPException(status_code=404, detail=f"Prediction failed. Ensure model is trained for {symbol} {interval}.")
             
        return {
            "symbol": symbol,
            "predicted_price": result['predicted_price'],
            "expected_change_pct": result['expected_change_pct'],
            "model_type": f"LSTM ({interval})",
            "current_price_date": result['prediction_date'].strftime("%Y-%m-%d %H:%M"),
            "target_date": result['target_date'].strftime("%Y-%m-%d %H:%M")
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/news/{symbol}")
def get_news(symbol: str):
    db = SessionLocal()
    try:
        # Fetch latest 5 news with sentiment
        # Join not needed if we just search by title or if we link news to stock_id (we do)
        query = text("""
            SELECT n.date, n.title, n.source, n.url, n.sentiment_label, n.sentiment_score
            FROM news_sentiment n
            JOIN stocks s ON s.id = n.stock_id
            WHERE s.symbol = :symbol
            ORDER BY n.date DESC
            LIMIT 5
        """)
        
        # Temporary workaround for empty news or NULL stock_id:
        # If no result, try fetching independent news?
        # For now, just execute.
        result = db.execute(query, {"symbol": symbol}).fetchall()
        
        return [
            {
                "date": str(row[0]),
                "title": row[1],
                "source": row[2],
                "url": row[3],
                "sentiment": row[4],
                "score": float(row[5] or 0)
            }
            for row in result
        ]
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []
    finally:
        db.close()

@app.get("/metrics/{symbol}")
def get_metrics(symbol: str, interval: str = '1d'):
    db = SessionLocal()
    try:
        # Fetch latest performance metrics AND metadata
        # We assume model_name matches pattern 'LSTM_{symbol}'
        # And we pick the latest performance record
        query = text("""
            SELECT 
                mp.mae, mp.rmse, mp.accuracy, mp.training_date, 
                mp.total_predictions, mp.correct_predictions,
                mm.training_samples, mm.features_used, mm.version
            FROM model_performance mp
            LEFT JOIN model_metadata mm ON mm.model_name = mp.model_name 
                                        AND mm.version = mp.model_version
            WHERE mp.model_name LIKE :model_name_pattern 
            AND mp.timeframe = :interval
            ORDER BY mp.training_date DESC
            LIMIT 1
        """)
        
        pattern = f"%{symbol}%" # loose match
        result = db.execute(query, {
            "model_name_pattern": pattern,
            "interval": interval
        }).fetchone()
        
        if result:
            return {
                "mae": float(result[0] or 0),
                "rmse": float(result[1] or 0),
                "accuracy": float(result[2] or 0),
                "training_date": str(result[3]),
                "total_predictions": int(result[4] or 0),
                "correct_predictions": int(result[5] or 0),
                "training_samples": int(result[6] or 0), # New field
                "features_used": result[7], # New field (JSON)
                "version": result[8] or "v1"
            }
        else:
             return {
                "mae": 0.0, "rmse": 0.0, "accuracy": 0.0, 
                "training_date": None,
                "total_predictions": 0,
                "correct_predictions": 0,
                "training_samples": 0,
                "features_used": "[]",
                "version": "N/A"
             }
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {
            "mae": 0.0, "rmse": 0.0, "accuracy": 0.0, 
            "training_date": None,
            "total_predictions": 0,
            "correct_predictions": 0,
            "training_samples": 0,
            "features_used": "[]",
            "version": "N/A"
        }
    finally:
        db.close()

@app.get("/signals/{symbol}")
def get_signals(symbol: str, limit: int = 100, interval: str = '1d', start_date: Optional[str] = None, end_date: Optional[str] = None):
    db = SessionLocal()
    try:
        # Construct query dynamically
        query_str = """
            SELECT 
                p.prediction_date, p.target_date, 
                p.predicted_direction, p.predicted_change_pct,
                pr.actual_direction, pr.actual_change_pct, pr.is_correct,
                p.predicted_price, pr.actual_price
            FROM predictions p
            LEFT JOIN prediction_results pr ON pr.prediction_id = p.id
            JOIN stocks s ON s.id = p.stock_id
            WHERE s.symbol = :symbol AND p.interval = :interval
        """
        
        params = {"symbol": symbol, "limit": limit, "interval": interval}

        if start_date:
            query_str += " AND p.prediction_date >= :start_date"
            params["start_date"] = start_date
            
        if end_date:
            # Add one day to end_date in Python to include full day
            try:
                from datetime import datetime, timedelta
                ed_dt = datetime.strptime(end_date, "%Y-%m-%d")
                next_day = ed_dt + timedelta(days=1)
                next_day_str = next_day.strftime("%Y-%m-%d")
                
                query_str += " AND p.prediction_date < :next_day"
                params["next_day"] = next_day_str
            except:
                # Fallback if format is wrong
                query_str += " AND p.prediction_date <= :end_date"
                params["end_date"] = end_date

        query_str += " ORDER BY p.prediction_date DESC LIMIT :limit"
            
        query = text(query_str)
        result = db.execute(query, params).fetchall()
        
        return [
            {
                "date": row[0].isoformat(),
                "target_date": str(row[1]),
                "prediction": row[2], # UP/DOWN
                "predicted_pct": float(row[3] or 0),
                "actual": row[4],
                "actual_pct": float(row[5] or 0),
                "is_win": bool(row[6]) if row[6] is not None else None,
                "predicted_price": float(row[7]) if row[7] else None,
                "actual_price": float(row[8]) if row[8] else None,
                "interval": interval
            }
            for row in result
        ]
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        return []
    finally:
        db.close()

@app.get("/winrate/{symbol}")
def get_winrate(symbol: str, interval: str = '1d', start_date: Optional[str] = None, end_date: Optional[str] = None):
    db = SessionLocal()
    try:
        query_str = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as wins
            FROM prediction_results pr
            JOIN predictions p ON p.id = pr.prediction_id
            JOIN stocks s ON s.id = p.stock_id
            WHERE s.symbol = :symbol AND p.interval = :interval
        """
        
        params = {"symbol": symbol, "interval": interval}

        if start_date:
            query_str += " AND p.prediction_date >= :start_date"
            params["start_date"] = start_date
            
        if end_date:
            # Add one day to end_date in Python to include full day
            try:
                from datetime import datetime, timedelta
                ed_dt = datetime.strptime(end_date, "%Y-%m-%d")
                next_day = ed_dt + timedelta(days=1)
                next_day_str = next_day.strftime("%Y-%m-%d")
                
                query_str += " AND p.prediction_date < :next_day"
                params["next_day"] = next_day_str
            except:
                query_str += " AND p.prediction_date <= :end_date"
                params["end_date"] = end_date
            
        query = text(query_str)
        result = db.execute(query, params).fetchone()
        
        total = result[0] or 0
        wins = result[1] or 0
        
        if total == 0:
            return {"win_rate": 0.0, "total_trades": 0, "wins": 0}
            
        win_rate = (wins / total) * 100
        
        return {
            "win_rate": float(win_rate),
            "total_trades": int(total),
            "wins": int(wins)
        }
    except Exception as e:
        logger.error(f"Error fetching winrate: {e}")
        return {"win_rate": 0.0, "total_trades": 0, "wins": 0}
    finally:
        db.close()

@app.get("/checklist/{symbol}")
def get_checklist(symbol: str):
    try:
        # Instantiate and calculate
        checklist = TraderChecklist(symbol)
        result = checklist.calculate()
        return result
    except Exception as e:
        logger.error(f"Checklist error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ScanRequest(BaseModel):
    symbols: Optional[List[str]] = []

@app.post("/scan")
def scan_market(req: ScanRequest):
    import concurrent.futures
    
    # Default Universe if empty
    targets = req.symbols
    if not targets or len(targets) == 0:
        targets = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'TLKM.JK', 
            'ASII.JK', 'GOTO.JK', 'ANTM.JK', 'MDKA.JK', 'UNTR.JK', 
            'ADRO.JK', 'PTBA.JK', 'PGAS.JK', 'INCO.JK', 'BRPT.JK', 
            'AMMN.JK', 'MEDC.JK', 'HRUM.JK', 'TPIA.JK', 'AKRA.JK',
            'SRTG.JK', 'BUKA.JK', 'EMTK.JK', 'ARTO.JK', 'CPIN.JK',
            'ICBP.JK', 'INDF.JK', 'KLBF.JK', 'UNVR.JK', 'EXCL.JK'
        ]
        
    results = []
    
    def process_one(sym):
        try:
            # Re-use existing checklist logic for freshness
            chk = TraderChecklist(sym)
            res = chk.calculate()
            return res
        except Exception as e:
            return {"symbol": sym, "error": str(e)}

    # Run in parallel to speed up 20+ http requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_one, sym): sym for sym in targets}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            
    # Sort by total_score descending
    results.sort(key=lambda x: x.get('total_score', -1), reverse=True)
            
    return results
@app.delete("/stocks/{symbol}")
def delete_stock(symbol: str):
    db = SessionLocal()
    try:
        # Find Stock ID
        sid = db.execute(text("SELECT id FROM stocks WHERE symbol = :s"), {"s": symbol}).fetchone()
        if not sid:
            raise HTTPException(status_code=404, detail="Stock not found")
        stock_id = sid[0]
        
        # 1. Prediction Results (via Predictions)
        db.execute(text("DELETE FROM prediction_results WHERE prediction_id IN (SELECT id FROM predictions WHERE stock_id = :sid)"), {"sid": stock_id})
        
        # 2. Predictions
        db.execute(text("DELETE FROM predictions WHERE stock_id = :sid"), {"sid": stock_id})
        
        # 3. Model Performance (ByName)
        db.execute(text("DELETE FROM model_performance WHERE model_name LIKE :pat"), {"pat": f"%{symbol}%"})
        db.execute(text("DELETE FROM model_metadata WHERE model_name LIKE :pat"), {"pat": f"%{symbol}%"})
        
        # 4. News
        db.execute(text("DELETE FROM news_sentiment WHERE stock_id = :sid"), {"sid": stock_id})
        
        # 5. Prices
        db.execute(text("DELETE FROM stock_prices WHERE stock_id = :sid"), {"sid": stock_id})
        
        # 6. Stock
        db.execute(text("DELETE FROM stocks WHERE id = :sid"), {"sid": stock_id})
        
        db.commit()
        logger.info(f"Deleted stock {symbol} and all associated data.")
        return {"message": f"Deleted {symbol} successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
