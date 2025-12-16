import yfinance as yf
import pandas as pd
import numpy as np
import ta

class TraderChecklist:
    def __init__(self, symbol):
        self.symbol = symbol
        self.scores = {
            "daily": 0, "hourly": 0, "15m": 0,
            "volume": 0, "catalyst": 0, "fundamental": 0
        }
        self.max_scores = {
            "daily": 25, "hourly": 25, "15m": 20,
            "volume": 15, "catalyst": 10, "fundamental": 5,
            "ml_suitability": 100 # New Metric
        }
        self.details = {
            "daily": [], "hourly": [], "15m": [],
            "volume": [], "catalyst": [], "fundamental": [],
            "ml_metrics": [] # New Details
        }
        self.metrics = {
             "avg_value_idr": 0,
             "volatility_pct": 0,
             "recommendation": "N/A"
        }
        self.data = {}
        self.info = {}

    def set_data(self, daily_df=None, hourly_df=None, m15_df=None):
        """Inject dataframes directly (e.g. from Database) to avoid API calls."""
        if daily_df is not None: self.data['1d'] = daily_df
        if hourly_df is not None: self.data['1h'] = hourly_df
        if m15_df is not None: self.data['15m'] = m15_df

    def fetch_data(self):
        # 0. Skip if data already injected (Hybrid Mode)
        if '1d' in self.data and '1h' in self.data and '15m' in self.data:
            return

        # 1. Fetch Info (Fundamentals)
        ticker = yf.Ticker(self.symbol)
        try:
            self.info = ticker.info
        except:
            self.info = {}

        # 2. Fetch Multi-Timeframe Data
        # Daily: Need enough for MA200 (approx 1 year workdays -> 250+. Fetch 2y)
        if '1d' not in self.data:
            self.data['1d'] = ticker.history(period="2y", interval="1d")
        
        # Hourly: Need enough for MA50 (approx 50h. 1 wk ~ 30h. Fetch 1mo)
        if '1h' not in self.data:
            self.data['1h'] = ticker.history(period="1mo", interval="1h")
        
        # 15m: Need enough for MA20 (20 * 15m = 300m = 5h. Fetch 5d)
        if '15m' not in self.data:
            self.data['15m'] = ticker.history(period="5d", interval="15m")

    def analyze_daily(self):
        df = self.data.get('1d')
        if df is None or len(df) < 200:
            self.details['daily'].append({"label": "Insufficient Data for MA200", "score": 0, "status": "FAIL"})
            return

        last_close = df['Close'].iloc[-1]
        
        # Calc Indicators
        sma_50 = ta.trend.sma_indicator(df['Close'], window=50).iloc[-1]
        sma_200 = ta.trend.sma_indicator(df['Close'], window=200).iloc[-1]
        
        # 1. Price > MA50 (8 pts)
        if last_close > sma_50:
            self.scores['daily'] += 8
            self.details['daily'].append({"label": "Price > MA50 (Daily)", "score": 8, "status": "PASS", "value": f"{last_close:.0f} > {sma_50:.0f}"})
        else:
            self.details['daily'].append({"label": "Price > MA50 (Daily)", "score": 0, "status": "FAIL", "value": f"{last_close:.0f} < {sma_50:.0f}"})

        # 2. Not Breakdown MA200 (6 pts)
        # "Tidak breakdown" -> Price > MA200
        if last_close > sma_200:
            self.scores['daily'] += 6
            self.details['daily'].append({"label": "Price > MA200 (Daily)", "score": 6, "status": "PASS", "value": f"Above {sma_200:.0f}"})
        else:
             self.details['daily'].append({"label": "Price > MA200 (Daily)", "score": 0, "status": "FAIL", "value": f"Below {sma_200:.0f}"})

        # 3. Structure (Higher Highs / Sideways-Up) (6 pts)
        # Simplified: SMA20 > SMA50 (Golden Cross area) OR Slope of SMA20 is positive
        sma_20 = ta.trend.sma_indicator(df['Close'], window=20)
        sma_20_curr = sma_20.iloc[-1]
        sma_20_prev = sma_20.iloc[-5] # 5 days ago
        
        if sma_20_curr > sma_20_prev or last_close > sma_20_curr:
            self.scores['daily'] += 6
            self.details['daily'].append({"label": "Structure Uptrend/Sideways", "score": 6, "status": "PASS", "value": "MA20 Rising/Price Active"})
        else:
            self.details['daily'].append({"label": "Structure Uptrend/Sideways", "score": 0, "status": "FAIL", "value": "MA20 Falling"})

        # 4. Performance 3-6mo > 0 (5 pts)
        # Approx 3 months = 60 trading days
        try:
            price_3mo = df['Close'].iloc[-60]
            if last_close > price_3mo:
                self.scores['daily'] += 5
                self.details['daily'].append({"label": "Performance 3mo > 0", "score": 5, "status": "PASS", "value": "Positive"})
            else:
                self.details['daily'].append({"label": "Performance 3mo > 0", "score": 0, "status": "FAIL", "value": "Negative"})
        except:
             pass

        # CRITICAL RULE: If Daily Bearish (Score < 10 maybe? Or Price < MA200?), STOP?
        # User guideline: "Daily bearish = STOP". 
        # Metric: If Price < MA200 and Price < MA50 -> Bearish.
        if last_close < sma_200 and last_close < sma_50:
            self.details['daily'].append({"label": "⚠️ CRITICAL: DAILY BEARISH", "score": 0, "status": "STOP", "value": "Price < MA50 & MA200"})
            # Invalidate all scores? Or just flag it. 
            # User said "Skor total otomatis tidak layak".
            # We will handle this in final summation.

    def analyze_hourly(self):
        df = self.data.get('1h')
        if df is None or len(df) < 50:
            self.details['hourly'].append({"label": "Insufficient Data", "score": 0, "status": "FAIL"})
            return

        last_close = df['Close'].iloc[-1]
        sma_20 = ta.trend.sma_indicator(df['Close'], window=20).iloc[-1]
        sma_50 = ta.trend.sma_indicator(df['Close'], window=50).iloc[-1]

        # 1. Price > MA20 & MA50 (8 pts)
        if last_close > sma_20 and last_close > sma_50:
            self.scores['hourly'] += 8
            self.details['hourly'].append({"label": "Price > MA20 & MA50 (1H)", "score": 8, "status": "PASS"})
        else:
             self.details['hourly'].append({"label": "Price > MA20 & MA50 (1H)", "score": 0, "status": "FAIL"})

        # 2. Higher Low (6 pts)
        # Check last 10 candles, is Low increasing?
        # Simplified: Low[-1] > Low[-10] or Linear Regression Slope of Low > 0
        lows = df['Low'].tail(10)
        slope = np.polyfit(range(len(lows)), lows, 1)[0]
        if slope > 0:
            self.scores['hourly'] += 6
            self.details['hourly'].append({"label": "Higher Lows", "score": 6, "status": "PASS", "value": "Slope +"})
        else:
            self.details['hourly'].append({"label": "Higher Lows", "score": 0, "status": "FAIL", "value": "Slope -"})

        # 3. Consolidation (Flag/Range) (6 pts)
        # BB Width small?
        bb_high = ta.volatility.bollinger_hband(df['Close'], window=20).iloc[-1]
        bb_low = ta.volatility.bollinger_lband(df['Close'], window=20).iloc[-1]
        bb_width_pct = (bb_high - bb_low) / sma_20 * 100
        
        # Interpretation: "Consolidation rapi" usually means low volatility before expansion, OR steady uptrend.
        # Let's check: if BB Width < 5% (tight) OR Price is making small candles.
        # Alternative: Just give points if not extremely overextended (RSI < 75)
        rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
        if rsi < 70 and slope > -10: # Not crash
            self.scores['hourly'] += 6
            self.details['hourly'].append({"label": "Consolidation / Healthy", "score": 6, "status": "PASS", "value": "RSI OK"})
        else:
            self.details['hourly'].append({"label": "Consolidation / Healthy", "score": 0, "status": "FAIL", "value": "Overextended/Choppy"})

        # 4. Volume Rise (5 pts)
        # Check if last candle (or recent green) has vol > avg
        last_vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        is_green = df['Close'].iloc[-1] > df['Open'].iloc[-1]
        
        if last_vol > avg_vol and is_green:
            self.scores['hourly'] += 5
            self.details['hourly'].append({"label": "Volume Validation", "score": 5, "status": "PASS", "value": "High Vol Green"})
        elif last_vol > avg_vol * 0.8: # Partial credit for decent volume
             self.scores['hourly'] += 3
             self.details['hourly'].append({"label": "Volume Validation", "score": 3, "status": "WARN", "value": "Med Vol"})
        else:
             self.details['hourly'].append({"label": "Volume Validation", "score": 0, "status": "FAIL", "value": "Low Vol"})

    def analyze_15m(self):
        df = self.data.get('15m')
        if df is None or len(df) < 20:
            self.details['15m'].append({"label": "Insufficient Data", "score": 0, "status": "FAIL"})
            return
            
        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high = df['High'].iloc[-1]
        
        # 1. Breakout High (8 pts)
        # Close near High of session/day?
        # Check max high of last 20 candles
        recent_high = df['High'].rolling(20).max().iloc[-1]
        if last_close >= recent_high * 0.99: # Within 1% of high
            self.scores['15m'] += 8
            self.details['15m'].append({"label": "Breakout / Near High", "score": 8, "status": "PASS"})
        else:
            self.details['15m'].append({"label": "Breakout / Near High", "score": 0, "status": "FAIL"})
            
        # 2. Pullback to MA20 (6 pts)
        # Price is above MA20 but close to it (e.g. < 2% away)
        sma_20 = ta.trend.sma_indicator(df['Close'], window=20).iloc[-1]
        dist_pct = (last_close - sma_20) / sma_20 * 100
        
        if last_close > sma_20 and dist_pct < 1.5: # 1.5% buffer for 'Pullback'
             self.scores['15m'] += 6
             self.details['15m'].append({"label": "Pullback MA20", "score": 6, "status": "PASS", "value": f"{dist_pct:.2f}% from MA"})
        elif last_close > sma_20:
             # It's above, but maybe extended. Give partial?
             self.scores['15m'] += 2
             self.details['15m'].append({"label": "Pullback MA20", "score": 2, "status": "WARN", "value": "Above but extended"})
        else:
             self.details['15m'].append({"label": "Pullback MA20", "score": 0, "status": "FAIL", "value": "Below MA20"})
             
        # 3. Strong Candle + Vol (6 pts)
        # Body > 50% of range, High Volume
        body = abs(last_close - last_open)
        rng = df['High'].iloc[-1] - df['Low'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        
        is_strong = (body > rng * 0.5) if rng > 0 else False
        is_vol = df['Volume'].iloc[-1] > avg_vol
        
        if is_strong and is_vol:
            self.scores['15m'] += 6
            self.details['15m'].append({"label": "Strong Candle & Vol", "score": 6, "status": "PASS"})
        else:
            self.details['15m'].append({"label": "Strong Candle & Vol", "score": 0, "status": "FAIL"})

    def analyze_volume(self):
        # 4. Volume & Liquidity (Max 15)
        # Uses Daily data usually for averages
        df = self.data.get('1d')
        if df is None: return
        
        last_close = df['Close'].iloc[-1]
        
        # 1. Avg Value Transaction > 1B (6 pts)
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        avg_value_idr = avg_vol * last_close
        if pd.isna(avg_value_idr): avg_value_idr = 0
        
        self.metrics['avg_value_idr'] = avg_value_idr # Store for ML Calc
        
        if avg_value_idr >= 1_000_000_000:
             self.scores['volume'] += 6
             self.details['volume'].append({"label": "Liquidity > 1B", "score": 6, "status": "PASS", "value": f"{avg_value_idr/1E9:.1f}B"})
        else:
             self.details['volume'].append({"label": "Liquidity > 1B", "score": 0, "status": "FAIL", "value": f"{avg_value_idr/1E9:.1f}B"})
             
        # 2. Vol Intraday > Avg (6 pts)
        vol = df['Volume'].iloc[-1]
        vol_ma = df['Volume'].rolling(20).mean().iloc[-1]
        if vol > vol_ma:
            self.scores['volume'] += 6
            self.details['volume'].append({"label": "Vol > MA20", "score": 6, "status": "PASS"})
        else:
            self.details['volume'].append({"label": "Vol > MA20", "score": 0, "status": "FAIL"})

        # --- ML SUITABILITY CALCULATION ---
        # 1. Liquidity (Must be > 10B IDR for Institutions, > 1B for Retail)
        # avg_value_idr already calc above
        
        # 2. Volatility (ATR %)
        # AI works best on 1.5% - 5% daily range. Too low = Dead. Too high = Gambling.
        atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
        atr_pct = (atr / last_close) * 100
        self.metrics['volatility_pct'] = atr_pct
        
        ml_score = 0
        reasons = []
        
        # Liquidity Check (Max 50)
        if avg_value_idr > 100_000_000_000: # > 100 Milyar (Blue Chip)
            ml_score += 50
            reasons.append("Ultra Liquid (Big Money)")
        elif avg_value_idr > 10_000_000_000: # > 10 Milyar (Liquid)
            ml_score += 40
            reasons.append("High Liquidity")
        elif avg_value_idr > 1_000_000_000: # > 1 Milyar (Mid)
            ml_score += 20
            reasons.append("Medium Liquidity")
        else:
            ml_score -= 50 # Penalty for illiquid
            reasons.append("Illiquid (Risky)")
            
        # Volatility Check (Max 50)
        if 1.5 <= atr_pct <= 6.0:
            ml_score += 50
            reasons.append("Healthy Volatility (Good for AI)")
        elif atr_pct > 6.0:
            ml_score += 30
            reasons.append("High Volatility (Hard/Risky)")
        elif atr_pct < 1.0:
            ml_score -= 20
            reasons.append("Low Volatility (Dead Stock)")
        else:
            ml_score += 20 # Default for other cases
            
        self.scores['ml_suitability'] = max(0, min(100, ml_score))
        self.max_scores['ml_suitability'] = 100 # Add max score for ML
        
        # Label
        if ml_score >= 80: rec = "⭐ PERFECT"
        elif ml_score >= 60: rec = "✅ GOOD"
        elif ml_score >= 40: rec = "⚠️ RISKY"
        else: rec = "🚫 AVOID"
        
        self.metrics['recommendation'] = rec
        self.details['ml_metrics'] = reasons
             
        # 3. Spread Wajar (3 pts)
        # Hard to get Real Spread from free API.
        # Proxy: High-Low range is decent (not 0) and not crazy wicks.
        # Assume Pass for now if liquid.
        if avg_value_idr > 5_000_000_000:
             self.scores['volume'] += 3
             self.details['volume'].append({"label": "Spread (Est.)", "score": 3, "status": "PASS", "value": "Liquid"})
        else:
             self.details['volume'].append({"label": "Spread (Est.)", "score": 0, "status": "FAIL", "value": "Illiquid risk"})

    def analyze_fundamental(self):
        # 6. Fundamental (Max 5)
        # 1. Revenue & EPS not red (3 pts)
        try:
            # yfinance info keys: 'trailingEps', 'totalRevenue' (just existence?), 'revenueGrowth', 'earningsGrowth'
            eps = self.info.get('trailingEps', 0)
            
            if eps > 0:
                self.scores['fundamental'] += 3
                self.details['fundamental'].append({"label": "EPS > 0", "score": 3, "status": "PASS", "value": f"{eps}"})
            else:
                self.details['fundamental'].append({"label": "EPS > 0", "score": 0, "status": "FAIL", "value": f"{eps}"})
        except:
             pass
             
        # 2. No debt extreme (2 pts)
        # DebtToEquity < 200?
        try:
            de = self.info.get('debtToEquity', 0)
            if de is not None and de < 200: # < 200%
                 self.scores['fundamental'] += 2
                 self.details['fundamental'].append({"label": "Debt Safe", "score": 2, "status": "PASS", "value": f"D/E {de}"})
            else:
                 self.details['fundamental'].append({"label": "Debt Safe", "score": 0, "status": "FAIL", "value": f"D/E {de}"})
        except:
             pass

    def analyze_catalyst(self):
         # 5. Catalyst (Max 10)
         # Using placeholder logic for now or simple check
         # "Sector hot" -> Hard to automate without comparison.
         # "News" -> Check if 'news' list in info is fresh.
         
         # Grant partial points to be generous if fundamental is ok
         # Or check recommendationKey
         rec = self.info.get('recommendationKey', 'none')
         if rec in ['buy', 'strong_buy']:
              self.scores['catalyst'] += 4
              self.details['catalyst'].append({"label": "Analyst Buy Rating", "score": 4, "status": "PASS"})
         
         # Sector check
         self.details['catalyst'].append({"label": "Sector Trend", "score": 3, "status": "INFO", "value": "Manual Check"})
         self.details['catalyst'].append({"label": "News Sentiment", "score": 3, "status": "INFO", "value": "See News Tab"})

    def calculate(self):
        self.fetch_data()
        self.analyze_daily()
        self.analyze_hourly()
        self.analyze_15m()
        self.analyze_volume()
        self.analyze_fundamental()
        self.analyze_catalyst()
        
        # Calculate Total Score (Excluding ML Suitability from the Trade Checklist 0-100)
        # We only sum the keys that are part of the original checklist
        checklist_keys = ['daily', 'hourly', '15m', 'volume', 'catalyst', 'fundamental']
        final_score = sum(self.scores.get(k, 0) for k in checklist_keys)
        
        # Decision
        decision = "🔴 TIDAK LAYAK"
        if final_score >= 75:
            decision = "🟢 LAYAK DITRADE (KUAT)"
        elif final_score >= 65:
            decision = "🟡 LAYAK (TUNGGU 15m)"
            
        # Overwrite if Daily is critical fail
        # Check if we logged a STOP
        for d in self.details['daily']:
            if d.get('status') == 'STOP':
                decision = "🔴 TIDAK LAYAK (Daily Bearish)"
                # Invalidate all scores? Or just flag it. 
                # User said "Skor total otomatis tidak layak".
                # We will handle this in final summation.
                decision = "🔴 TIDAK LAYAK (Daily Bearish)"
                
        return {
            "symbol": self.symbol,
            "total_score": final_score,
            "decision": decision,
            "scores": self.scores,
            "max_scores": self.max_scores,
            "details": self.details,
            "metrics": self.metrics # New Export
        }
