import pandas as pd
import ta
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.utils.logger import get_logger

logger = get_logger()

class TechnicalIndicators:
    def __init__(self, db: Session):
        self.db = db

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators for a dataframe containing OHLCV data.
        """
        try:
            df = df.copy()
            # Ensure proper types
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)

            # RSI
            df['rsi_14'] = ta.momentum.rsi(df['close'], window=14)

            # MACD
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_hist'] = macd.macd_diff()

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()

            # SMAs
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            df['sma_200'] = ta.trend.sma_indicator(df['close'], window=200)

            # EMAs
            df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
            df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)

            # Volume SMA
            df['volume_sma_20'] = ta.trend.sma_indicator(df['volume'], window=20)

            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            raise

    def process_and_save(self, stock_id: int):
        """Fetch prices from DB, calculate indicators, and save back."""
        try:
            # 1. Fetch prices
            query = text("""
                SELECT date, open, high, low, close, volume 
                FROM stock_prices 
                WHERE stock_id = :stock_id 
                ORDER BY date ASC
            """)
            result = self.db.execute(query, {"stock_id": stock_id})
            data = result.fetchall()
            
            if not data:
                logger.warning(f"No price data found for stock_id {stock_id}")
                return

            df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index('date', inplace=True)

            # 2. Calculate
            df_indicators = self.calculate_indicators(df)
            
            # 3. Save
            count = 0
            for date, row in df_indicators.iterrows():
                try:
                    self.db.execute(
                        text("""
                            INSERT INTO technical_indicators (
                                stock_id, date, rsi_14, macd, macd_signal, macd_hist,
                                bb_upper, bb_middle, bb_lower, sma_20, sma_50, sma_200,
                                ema_12, ema_26, volume_sma_20
                            ) VALUES (
                                :stock_id, :date, :rsi, :macd, :macd_sig, :macd_hist,
                                :bb_up, :bb_mid, :bb_low, :sma20, :sma50, :sma200,
                                :ema12, :ema26, :vol_sma20
                            )
                            ON CONFLICT (stock_id, date) DO UPDATE 
                            SET rsi_14=:rsi, macd=:macd, macd_signal=:macd_sig, macd_hist=:macd_hist,
                                bb_upper=:bb_up, bb_middle=:bb_mid, bb_lower=:bb_low,
                                sma_20=:sma20, sma_50=:sma50, sma_200=:sma200,
                                ema_12=:ema12, ema_26=:ema26, volume_sma_20=:vol_sma20
                        """),
                        {
                            "stock_id": stock_id,
                            "date": date,
                            "rsi": row['rsi_14'] if pd.notna(row['rsi_14']) else None,
                            "macd": row['macd'] if pd.notna(row['macd']) else None,
                            "macd_sig": row['macd_signal'] if pd.notna(row['macd_signal']) else None,
                            "macd_hist": row['macd_hist'] if pd.notna(row['macd_hist']) else None,
                            "bb_up": row['bb_upper'] if pd.notna(row['bb_upper']) else None,
                            "bb_mid": row['bb_middle'] if pd.notna(row['bb_middle']) else None,
                            "bb_low": row['bb_lower'] if pd.notna(row['bb_lower']) else None,
                            "sma20": row['sma_20'] if pd.notna(row['sma_20']) else None,
                            "sma50": row['sma_50'] if pd.notna(row['sma_50']) else None,
                            "sma200": row['sma_200'] if pd.notna(row['sma_200']) else None,
                            "ema12": row['ema_12'] if pd.notna(row['ema_12']) else None,
                            "ema26": row['ema_26'] if pd.notna(row['ema_26']) else None,
                            "vol_sma20": row['volume_sma_20'] if pd.notna(row['volume_sma_20']) else None
                        }
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Error saving indicators for {date}: {e}")
            
            self.db.commit()
            logger.info(f"Updated {count} indicator records for stock_id {stock_id}")

        except Exception as e:
            logger.error(f"Failed to process indicators for stock_id {stock_id}: {e}")
            self.db.rollback()
