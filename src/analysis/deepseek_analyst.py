import os
import yfinance as yf
import pandas as pd
import ta
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class DeepSeekAnalyst:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.system_prompt_path = "DeepSeekSytemPrompt.md"

    def _get_system_prompt(self):
        try:
            with open(self.system_prompt_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback if file not found (though it should exist)
            return "You are a professional stock trading analyst. Analyze the provided data top-down."

    def _fetch_data(self, symbol):
        """Fetch Daily, H1, and M15 data."""
        data = {}
        
        # 1. Daily (Context)
        # Fetch enough for MA200 calculation
        df_d = yf.download(symbol, period="2y", interval="1d", progress=False)
        if not df_d.empty:
            data['daily'] = self._process_indicators(df_d)
        else:
            return None

        # 2. Hourly (Validation)
        df_h1 = yf.download(symbol, period="3mo", interval="1h", progress=False)
        if not df_h1.empty:
            data['h1'] = self._process_indicators(df_h1)
        
        # 3. M15 (Execution)
        df_m15 = yf.download(symbol, period="1mo", interval="15m", progress=False)
        if not df_m15.empty:
             data['m15'] = self._process_indicators(df_m15)
             
        return data

    def _process_indicators(self, df):
        """Add Technical Indicators (MA, RSI)."""
        # Ensure flat columns if MultiIndex (yfinance new version)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Basic Cleanup
        df = df.copy()
        df = df.sort_index()
        
        # MA
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        
        # RSI
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        
        # Return last 5 candles for context
        return df.tail(5)

    def _format_data_string(self, symbol, data):
        """Format data into readable text for the LLM."""
        txt = f"ANALYSIS DATA FOR {symbol}:\n\n"
        
        if 'daily' in data:
            d = data['daily'].iloc[-1]
            txt += "--- TIMEFRAME DAILY (1D) ---\n"
            txt += f"Last Price: {d['Close']:.0f}\n"
            txt += f"MA20: {d['MA20']:.0f} | MA50: {d['MA50']:.0f} | MA200: {d['MA200']:.0f}\n"
            txt += f"RSI: {d['RSI']:.1f}\n"
            txt += "Recent Candles (Last 3):\n"
            for i in range(3, 0, -1):
                row = data['daily'].iloc[-i]
                txt += f"  {row.name.strftime('%Y-%m-%d')}: O={row['Open']:.0f} H={row['High']:.0f} L={row['Low']:.0f} C={row['Close']:.0f}\n"
            txt += "\n"

        if 'h1' in data:
            h = data['h1'].iloc[-1]
            txt += "--- TIMEFRAME HOURLY (H1) ---\n"
            txt += f"Last Price: {h['Close']:.0f}\n"
            txt += f"MA20: {h['MA20']:.0f} | MA50: {h['MA50']:.0f}\n"
            txt += f"RSI: {h['RSI']:.1f}\n"
            txt += "Recent Candles (Last 3):\n"
            for i in range(3, 0, -1):
                row = data['h1'].iloc[-i]
                txt += f"  {row.name.strftime('%d %H:%M')}: C={row['Close']:.0f}\n"
            txt += "\n"
            
        if 'm15' in data:
            m = data['m15'].iloc[-1]
            txt += "--- TIMEFRAME 15 MIN (M15) ---\n"
            txt += f"Last Price: {m['Close']:.0f}\n"
            txt += f"MA20: {m['MA20']:.0f}\n"
            txt += f"RSI: {m['RSI']:.1f}\n"
            txt += "Recent Candles (Last 3):\n"
            for i in range(3, 0, -1):
                row = data['m15'].iloc[-i]
                txt += f"  {row.name.strftime('%d %H:%M')}: C={row['Close']:.0f}\n"
            txt += "\n"
            
        return txt

    def analyze_stock(self, symbol):
        """Main method to perform analysis."""
        print(f"🤖 AI Analyst: Fetching data for {symbol}...")
        data = self._fetch_data(symbol)
        
        if not data or 'daily' not in data:
            return "Error: Insufficient data for analysis."
            
        data_str = self._format_data_string(symbol, data)
        system_prompt = self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please analyze {symbol} based on the following data:\n\n{data_str}"}
        ]
        
        print("🤖 AI Analyst: Querying DeepSeek API...")
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.3, # Low temp for analytical precision
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI Error: {str(e)}"

if __name__ == "__main__":
    # Test Run
    analyst = DeepSeekAnalyst()
    print(analyst.analyze_stock("BBCA.JK"))
