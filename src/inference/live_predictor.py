import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import datetime, timedelta
from src.utils.database import SessionLocal
from src.utils.logger import get_logger
from src.models.lstm_model import LSTMModel
from src.feature_engineering.preprocessing import DataPreprocessor
import os

logger = get_logger()

class LivePredictor:
    def __init__(self, db_session):
        self.db = db_session

    def predict_and_save(self, symbol: str, interval: str):
        """
        Run inference for a specific symbol and interval using the latest data.
        Saves the prediction to the database.
        """
        try:
            # 1. Get Stock ID
            stock_id = self.db.execute(
                text("SELECT id FROM stocks WHERE symbol = :symbol"),
                {"symbol": symbol}
            ).fetchone()
            
            if not stock_id:
                logger.error(f"LivePredictor: Stock {symbol} not found in DB.")
                return
            stock_id = stock_id[0]

            # 2. Check if model exists
            model_path = f"data/models/{symbol}_{interval}_lstm.h5"
            if not os.path.exists(model_path):
                # Silent return or debug log - valid case if model not trained yet
                # logger.debug(f"LivePredictor: No model found for {symbol} {interval}. Skipping.")
                return

            # 3. Fetch Data (Need last 300 rows for indicators + sequence)
            query = text("""
                SELECT timestamp, open, high, low, close, volume
                FROM stock_prices 
                WHERE stock_id = :sid AND interval = :interval
                ORDER BY timestamp DESC
                LIMIT 300
            """)
            res = self.db.execute(query, {"sid": stock_id, "interval": interval}).fetchall()
            
            if len(res) < 60:
                logger.warning(f"LivePredictor: Insufficient data for {symbol} {interval} (Need >60).")
                return

            # Convert to DF and toggle to Ascending (Old -> New)
            df = pd.DataFrame(res, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.iloc[::-1].sort_values('timestamp')
            df.set_index('timestamp', inplace=True)

            # --- SENTIMENT SCORE ---
            try:
                # Fetch latest sentiment for symbol
                s_query = text("""
                    SELECT sentiment_score FROM news_sentiment ns
                    JOIN stocks s ON s.id = ns.stock_id
                    WHERE s.symbol = :sym
                    ORDER BY ns.date DESC LIMIT 1
                """)
                s_res = self.db.execute(s_query, {"sym": symbol}).fetchone()
                current_sentiment = float(s_res[0]) if s_res else 0.0
            except Exception as e:
                logger.warning(f"LivePredictor sentiment fetch failed: {e}")
                current_sentiment = 0.0
            
            df['sentiment_score'] = current_sentiment

            # 4. Feature Engineering
            from src.feature_engineering.technical_indicators import TechnicalIndicators
            ti = TechnicalIndicators(self.db)
            df = ti.calculate_indicators(df)
            
            # --- MACRO DATA MERGING ---
            # Fetch ^JKSE and IDR=X data to match Trainer logic
            macro_featuers = []
            
            # Helper to fetch macro
            def fetch_macro(macro_symbol, col_name):
                try:
                    mid = self.db.execute(text("SELECT id FROM stocks WHERE symbol=:s"), {"s": macro_symbol}).fetchone()
                    if mid:
                        m_query = text("""
                            SELECT timestamp, close 
                            FROM stock_prices 
                            WHERE stock_id = :sid AND interval = :interval 
                            ORDER BY timestamp DESC LIMIT 300
                        """)
                        m_res = self.db.execute(m_query, {"sid": mid[0], "interval": interval}).fetchall()
                        if m_res:
                            m_df = pd.DataFrame(m_res, columns=['timestamp', col_name])
                            m_df['timestamp'] = pd.to_datetime(m_df['timestamp'])
                            m_df.set_index('timestamp', inplace=True)
                            return m_df
                except Exception as e:
                    logger.warning(f"LivePredictor failed to fetch macro {macro_symbol}: {e}")
                return None

            ihsg_df = fetch_macro('^JKSE', 'ihsg_close')
            usd_df = fetch_macro('IDR=X', 'usd_close')
            
            if ihsg_df is not None:
                df = pd.merge(df, ihsg_df, left_index=True, right_index=True, how='left')
                df['ihsg_close'] = df['ihsg_close'].fillna(method='ffill')
            else:
                df['ihsg_close'] = 0.0
                
            if usd_df is not None:
                df = pd.merge(df, usd_df, left_index=True, right_index=True, how='left')
                df['usd_close'] = df['usd_close'].fillna(method='ffill')
            else:
                df['usd_close'] = 0.0

            df.fillna(method='bfill', inplace=True)
            df.fillna(0, inplace=True)

            # 5. Preprocess
            # Define standard features list used in training
            features = ['close', 'volume', 'open', 'high', 'low', 
                       'rsi_14', 'macd', 'macd_signal', 
                       'bb_upper', 'bb_lower', 
                       'sentiment_score', 'ihsg_close', 'usd_close']

            preprocessor = DataPreprocessor(sequence_length=60)
            
            # Try to load saved scaler
            scaler_path = f"data/models/{symbol}_{interval}_scaler.joblib"
            if os.path.exists(scaler_path):
                 try:
                     preprocessor.load(scaler_path)
                     scaled_df = preprocessor.transform(df, features)
                     logger.info(f"Loaded scaler from {scaler_path}")
                 except Exception as e:
                     logger.error(f"Failed to load scaler {scaler_path}: {e}. Fallback to fit_transform (WARNING: inconsistent scaling).")
                     scaled_df = preprocessor.fit_transform(df, features)
            else:
                logger.warning(f"Scaler not found at {scaler_path}. Fallback to fit_transform (WARNING: inconsistent scaling).")
                scaled_df = preprocessor.fit_transform(df, features)
            
            if len(scaled_df) < 60: return

            # Shape input: (1, 60, n_features)
            X = scaled_df[features].values[-60:].reshape(1, 60, len(features))
            
            # 6. Predict
            model = LSTMModel.load(model_path)
            pred_scaled = model.predict(X)
            
            # Unscale Prediction
            # CRITICAL FIX: Must use the SAME scaler parameters from training (Global Min/Max)
            # instead of the local 60-candle window Min/Max.
            
            pred_val = float(pred_scaled[0][0])
            pred_price = 0.0
            
            if hasattr(preprocessor, 'scaler') and hasattr(preprocessor.scaler, 'min_'):
                # Formula: X = (X_scaled - min_) / scale_
                # Assuming 'close' is the first feature (index 0)
                idx = 0 
                # Safety check for index
                if idx < len(preprocessor.scaler.scale_):
                    scale = preprocessor.scaler.scale_[idx]
                    min_val = preprocessor.scaler.min_[idx]
                    pred_price = (pred_val - min_val) / scale
                else:
                    # Fallback if scaler weird
                    close_min = float(df['close'].min())
                    close_max = float(df['close'].max())
                    pred_price = pred_val * (close_max - close_min) + close_min
            else:
                 # Fallback (Manual Local Unscale - only if scaler failed to load)
                 close_min = float(df['close'].min())
                 close_max = float(df['close'].max())
                 pred_price = pred_val * (close_max - close_min) + close_min
            
            current_close = float(df['close'].iloc[-1])
            expected_change_pct = ((pred_price - current_close) / current_close) * 100
            
            direction = "UP" if expected_change_pct > 0 else "DOWN"
            
            # 7. Save to DB
            # Determining Prediction Date (Now) and Target Date (Future)
            # Logic: If current data is 10:00 (Close), we predict 10:15.
            last_timestamp = df.index[-1] # e.g. 10:00
            prediction_date = last_timestamp # The moment prediction is made (based on data available)
            
            # Calculate Target Date (Smart Break Handling)
            delta = timedelta(minutes=15)
            if interval == '1h': delta = timedelta(hours=1)
            elif interval == '1m': delta = timedelta(minutes=1)
            elif interval == '1d': delta = timedelta(days=1)
            
            target_date = last_timestamp + delta
            
            # Correction for IDX Lunch Break (Mon-Thu: 12:00-13:30, Fri: 11:30-14:00)
            # Simple heuristic: If target lands in 12:00-13:00 range, push to 13:30 (Session 2 Open)
            if interval in ['15m', '1m', '1h']:
                # Mon-Thu (Days 0-3)
                if target_date.weekday() <= 3:
                     # If calculates to 12:00 or 12:xx, push to 13:30
                     if target_date.hour == 12:
                         target_date = target_date.replace(hour=13, minute=30)
                # Friday (Day 4)
                elif target_date.weekday() == 4:
                     # Break 11:30 - 14:00
                     if (target_date.hour == 11 and target_date.minute >= 30) or \
                        (target_date.hour in [12, 13]):
                         target_date = target_date.replace(hour=14, minute=0)

            # Insert into predictions
            query_ins = text("""
                INSERT INTO predictions (stock_id, prediction_date, target_date, interval, predicted_price, predicted_direction, predicted_change_pct, model_version)
                VALUES (:sid, :pd, :td, :intv, :pp, :pdir, :ppct, 'v_live')
                ON CONFLICT (stock_id, prediction_date, interval) 
                DO UPDATE SET predicted_price=EXCLUDED.predicted_price, predicted_direction=EXCLUDED.predicted_direction
            """)
            
            self.db.execute(query_ins, {
                "sid": stock_id,
                "pd": prediction_date,
                "td": target_date,
                "intv": interval,
                "pp": pred_price,
                "pdir": direction,
                "ppct": expected_change_pct
            })
            self.db.commit()
            
            logger.info(f"✨ Live Prediction Saved: {symbol} ({interval}) -> {direction} {expected_change_pct:.2f}% (Target: {pred_price:.0f})")

            # 8. Trigger Evaluation of Past Pending Predictions
            self.evaluate_past_predictions(stock_id, symbol, interval)
            
            return {
                "symbol": symbol,
                "predicted_price": float(pred_price),
                "expected_change_pct": float(expected_change_pct),
                "direction": direction,
                "model_version": "LSTM_v1", # FIXME: dynamic version
                "prediction_date": prediction_date,
                "target_date": target_date
            }

        except Exception as e:
            logger.error(f"LivePredictor Error {symbol}: {e}")
            self.db.rollback()

    def evaluate_past_predictions(self, stock_id: int, symbol: str, interval: str):
        """
        Check pending predictions (target_date passed) and verify against actual content.
        """
        try:
            # 1. Find pending predictions whose target_date is in the past
            # And that do NOT have a result yet.
            # Using LEFT JOIN to find missing results.
            # 1. Find pending predictions whose target_date is in the past
            # We fetch target_date directly from DB to assume Smart Break logic was applied during creation.
            query_pending = text("""
                SELECT p.id, p.prediction_date, p.interval, p.predicted_direction, p.predicted_price, p.target_date
                FROM predictions p
                LEFT JOIN prediction_results pr ON p.id = pr.prediction_id
                WHERE p.stock_id = :sid 
                AND p.target_date < NOW() 
                AND pr.id IS NULL
                LIMIT 50
            """)
            
            pending = self.db.execute(query_pending, {"sid": stock_id}).fetchall()
            
            if not pending:
                return

            # 2. For each pending prediction, verify
            count = 0
            for row in pending:
                pred_id, pred_date, pred_interval, pred_dir, pred_price, target_date_db = row
                pred_price = float(pred_price)
                
                # Use the stored Target Date (which already handles breaks/weekends)
                # Ensure it is datetime
                if isinstance(target_date_db, str):
                    real_target_date = datetime.strptime(target_date_db, "%Y-%m-%d %H:%M:%S")
                else:
                    real_target_date = target_date_db
                
                # Fetch Actual Price at Target Timestamp
                q_actual = text("""
                    SELECT close FROM stock_prices 
                    WHERE stock_id = :sid AND timestamp = :tdate
                """)
                actual_res = self.db.execute(q_actual, {"sid": stock_id, "tdate": real_target_date}).fetchone()
                
                if not actual_res:
                    # Maybe data not collected yet? Skip.
                    continue
                    
                actual_price = float(actual_res[0])
                
                # Calculate Result
                # We need Entry Price. Entry was at 'prediction_date'. 
                # But we can simpler check: 
                # Direction Correct: if (Predicted UP and Actual > Entry) ?
                # The prediction row stores 'predicted_direction'.
                # Wait, 'predicted_direction' logic was: "UP if Target > Current".
                
                # We need to know if Actual went in that direction relative to Entry.
                # We can re-fetch Entry (prediction_date) price OR rely on logic.
                # Let's verify strictly: Correct if Actual Direction matches Predicted Direction.
                # Actual Direction = (Actual Price > Entry Price) -> UP.
                # Wait, we need Entry Price.
                # Let's fetch entry price roughly?
                # Actually, simpler metric:
                # Error % = abs(Pred Price - Actual Price) / Actual Price
                
                # Is Correct? 
                # If Pred UP and Actual > Entry.
                # We assume Entry is roughly (Pred Price / (1 + change%)).
                # Better: Just check if Actual Price is closer to Predicted Price?
                # No, Direction is key.
                
                # Let's fetch current_close at prediction_time to be sure.
                # Fetch current_close at prediction_time (Entry Price)
                # Timestamp Logic (YFinance/StockPrices):
                # Row "10:00" contains Close for 10:00-10:15.
                # Prediction made at 10:00 uses data ending at 10:00 (Row "09:45").
                # So Entry Price = Close(Row P-Interval).
                
                delta_entry = timedelta(minutes=15)
                if pred_interval == '1h': delta_entry = timedelta(hours=1)
                elif pred_interval == '1m': delta_entry = timedelta(minutes=1)
                elif pred_interval == '1d': delta_entry = timedelta(days=1)
                
                entry_date = pred_date - delta_entry
                
                q_price_entry = text("SELECT close FROM stock_prices WHERE stock_id=:sid AND timestamp=:t")
                entry_res = self.db.execute(q_price_entry, {"sid": stock_id, "t": entry_date}).fetchone()
                
                if not entry_res: continue
                entry_price = float(entry_res[0])
                
                actual_dir_val = "UP" if actual_price > entry_price else "DOWN"
                is_correct = (actual_dir_val == pred_dir)
                actual_pct = (actual_price - entry_price) / entry_price * 100
                error_pct = abs(pred_price - actual_price) / actual_price * 100
                
                # Insert Result
                q_ins_res = text("""
                    INSERT INTO prediction_results (prediction_id, actual_direction, actual_change_pct, actual_price, is_correct, error_pct, evaluated_at)
                    VALUES (:pid, :adir, :apct, :aprice, :correct, :err, NOW())
                """)
                
                self.db.execute(q_ins_res, {
                    "pid": pred_id,
                    "adir": actual_dir_val,
                    "apct": actual_pct,
                    "aprice": actual_price,
                    "correct": is_correct,
                    "err": error_pct
                })
                count += 1
            
            if count > 0:
                self.db.commit()
                logger.info(f"✅ Verified {count} past predictions for {symbol}")
                
        except Exception as e:
            logger.error(f"Failed to evaluate past predictions for {symbol}: {e}")
            # Don't rollback main transaction if this fails, try-catched mostly independent.
            # But we share session.
            # safe to rollback here?
            pass
