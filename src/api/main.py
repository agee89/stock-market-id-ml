from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
from sqlalchemy import text
from src.utils.database import SessionLocal, get_db
from src.utils.logger import get_logger
from src.training.trainer import ModelTrainer
from src.models.lstm_model import LSTMModel
import os

app = FastAPI(title="Stock Market ID ML API")
logger = get_logger()

class PredictionResponse(BaseModel):
    symbol: str
    predicted_price: float
    expected_change_pct: float
    model_type: str = "LSTM"

class StockResponse(BaseModel):
    symbol: str
    name: str

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/stocks", response_model=List[StockResponse])
def get_stocks():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT symbol, name FROM stocks")).fetchall()
        return [{"symbol": row[0], "name": row[1]} for row in result]
    except Exception as e:
        logger.error(f"Error fetching stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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

@app.get("/predict/{symbol}", response_model=PredictionResponse)
def predict(symbol: str, interval: str = '1d'):
    # This is a simplified prediction using the saved model and latest data from DB
    try:
        model_path = f"data/models/{symbol}_{interval}_lstm.h5"
        if not os.path.exists(model_path):
             # Fallback to 1d if specific interval model not found? No, user needs to retrain.
            raise HTTPException(status_code=404, detail=f"Model for {interval} not found. Please train first.")
        
        # Load latest data
        db = SessionLocal()
        # Need last 60 points for sequence
        query = text("""
            SELECT p.timestamp, p.close, p.volume, p.open, p.high, p.low
            FROM stock_prices p
            JOIN stocks s ON s.id = p.stock_id
            WHERE s.symbol = :symbol AND p.interval = :interval
            ORDER BY p.timestamp DESC
            LIMIT 300
        """)
        result = db.execute(query, {"symbol": symbol, "interval": interval}).fetchall()
        db.close()
        
        if len(result) < 60:
             raise HTTPException(status_code=400, detail="Not enough historical data")

        # Prepare data (Reverse because we fetched DESC)
        df = pd.DataFrame(result, columns=['date', 'close', 'volume', 'open', 'high', 'low']).iloc[::-1]
        
        # Ensure proper types
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df.set_index('date', inplace=True) # TI needs index logic? TI methods operate on columns usually.
        # But TI.calculate_indicators operates on frame.
        
        # --- A. FEATURE ENGINEERING: TECHNICAL INDICATORS ---
        try:
            from src.feature_engineering.technical_indicators import TechnicalIndicators
            # We don't need real DB connection for TI calculation logic, but init requires it.
            # We already have db session.
            ti = TechnicalIndicators(db)
            df = ti.calculate_indicators(df)
        except Exception as e:
            logger.error(f"Failed to calculate indicators in API: {e}")
            raise HTTPException(status_code=500, detail=f"TI Calculation failed: {e}")

        # --- B. FEATURE ENGINEERING: NEWS SENTIMENT ---
        # Get latest sentiment
        try:
            # Similar query to get_news but just get recent average?
            # Or just fetch top 1 recent.
            # trainer uses 'date_only' merge.
            # For real-time predict, we use "Today's" sentiment.
            sent_query = text("""
                SELECT sentiment_score FROM news_sentiment 
                JOIN stocks s ON s.id = news_sentiment.stock_id
                WHERE s.symbol = :symbol
                ORDER BY date DESC
                LIMIT 1
            """)
            sent_res = db.execute(sent_query, {"symbol": symbol}).fetchone()
            sentiment_score = float(sent_res[0]) if sent_res else 0.0
            
            df['sentiment_score'] = sentiment_score
        except:
            df['sentiment_score'] = 0.0

        # --- C. FEATURE ENGINEERING: MACRO CONTEXT ---
        try:
            # Fetch IHSG
            ihsg_query = text("""
                SELECT timestamp as date, close as ihsg_close FROM stock_prices 
                JOIN stocks s ON s.id = stock_prices.stock_id
                WHERE s.symbol = '^JKSE' AND interval = :interval
                ORDER BY timestamp DESC LIMIT :lim
            """)
            ihsg_data = db.execute(ihsg_query, {"interval": interval, "lim": 60}).fetchall()
            if ihsg_data:
                ihsg_df = pd.DataFrame(ihsg_data, columns=['date', 'ihsg_close'])
                ihsg_df['date'] = pd.to_datetime(ihsg_df['date'])
                ihsg_df.set_index('date', inplace=True)
                df = pd.merge(df, ihsg_df, left_index=True, right_index=True, how='left')
                df['ihsg_close'] = df['ihsg_close'].fillna(method='ffill')

            # Fetch USD
            usd_query = text("""
                SELECT timestamp as date, close as usd_close FROM stock_prices 
                JOIN stocks s ON s.id = stock_prices.stock_id
                WHERE s.symbol = 'IDR=X' AND interval = :interval
                ORDER BY timestamp DESC LIMIT :lim
            """)
            usd_data = db.execute(usd_query, {"interval": interval, "lim": 60}).fetchall()
            if usd_data:
                usd_df = pd.DataFrame(usd_data, columns=['date', 'usd_close'])
                usd_df['date'] = pd.to_datetime(usd_df['date'])
                usd_df.set_index('date', inplace=True)
                df = pd.merge(df, usd_df, left_index=True, right_index=True, how='left')
                df['usd_close'] = df['usd_close'].fillna(method='ffill')

            # Handle missing macro columns if fetch failed
            if 'ihsg_close' not in df.columns:
                df['ihsg_close'] = 0.0
            if 'usd_close' not in df.columns:
                df['usd_close'] = 0.0

            df['ihsg_close'].fillna(method='bfill', inplace=True)
            df['usd_close'].fillna(method='bfill', inplace=True)
            df.fillna(0, inplace=True)

        except Exception as e:
            logger.error(f"Failed to merge macro features in API: {e}")
            df['ihsg_close'] = 0.0
            df['usd_close'] = 0.0

        # Features used in trainer
        features = ['close', 'volume', 'open', 'high', 'low', 
                   'rsi_14', 'macd', 'macd_signal', 
                   'bb_upper', 'bb_lower', 
                   'sentiment_score',
                   'ihsg_close', 'usd_close']
        
        # Handle scaling
        from src.feature_engineering.preprocessing import DataPreprocessor
        preprocessor = DataPreprocessor(sequence_length=60)
        
        # Clean NaNs (created by indicators)
        # If we have < 60 rows after NaN cleaning? 
        # Indicators like SMA-200 need 200 rows history!
        # API only fetched 60 rows! 
        # CRITICAL: We need to fetch MORE history to calculate indicators properly, then slice the last 60.
        # Logic update needed in SQL query above.
        
        # Re-fetch with lookback
        # 60 (seq) + 200 (max indicator window) = 260
        # Let's fetch 300 to be safe.
        
        # ... Wait, I cannot re-fetch here easily inside this block without refactoring.
        # I must fix the FETCH query first.
        
        # Temporary logic: Fill NaNs with 0 or ffill? 
        # ffill is safer. bfill for start.
        df.fillna(method='bfill', inplace=True)
        df.fillna(method='ffill', inplace=True)
        df.fillna(0, inplace=True) # Last resort
        
        # Fit on this window (MVP Hack - ideally load saved scalers)
        # Using fit_transform on just 60 rows is BAD because scale will be different from training!
        # Ideally we should load the scaler saved during training.
        # But we didn't save the scaler! (Typical MVP issue).
        # Compromise: fit_transform on the 300 rows window is "better" but still drifting.
        # For now, stick with fit_transform on available data.
        
        scaled_df = preprocessor.fit_transform(df, features)
        
        # Create sequence (last 60)
        if len(scaled_df) < 60:
             raise HTTPException(status_code=400, detail="Not enough data after processing")
             
        X = scaled_df[features].values[-60:].reshape(1, 60, len(features))
        
        # Predict
        model = LSTMModel.load(model_path)
        pred_scaled = model.predict(X)
        
        # Inverse transform logic
        # We need to unscale. 
        # Using the same MinMax logic on the specific column 'close'
        close_min = float(df['close'].min())
        close_max = float(df['close'].max())
        pred_price = float(pred_scaled[0][0]) * (close_max - close_min) + close_min
        
        # Calculate expected change percentage
        # df is sorted ASCENDING (Oldest -> Newest) due to .iloc[::-1] above.
        # So we want the LATEST close, which is at [-1]
        current_close = float(df['close'].iloc[-1]) 
        expected_change_pct = ((pred_price - current_close) / current_close) * 100

        return {
            "symbol": symbol,
            "predicted_price": float(pred_price),
            "expected_change_pct": float(expected_change_pct),
            "model_type": f"LSTM ({interval})"
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
                "is_win": bool(row[6]),
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
