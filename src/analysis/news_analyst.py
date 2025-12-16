import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger()

class DeepSeekNewsAnalyst:
    """
    Dedicated Analyst for Quantitative News Sentiment Scoring.
    Uses DeepSeek AI to convert text headlines into numerical sentiment scores.
    """
    def __init__(self):
        # 1. Robust .env loading
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(dotenv_path=env_path)

        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.deepseek.com"
        
        if not self.api_key:
            logger.warning("⚠️ DEEPSEEK_API_KEY not found. News Analysis will return Neutral (0.0).")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
        # Dedicated System Prompt for News Scoring
        self.system_prompt = (
            "You are a Quantitative Financial Sentiment Analyzer Agent.\n"
            "Your ONLY purpose is to read headlines and output a single floating point number.\n"
            "You do NOT explain. You do NOT chat. You only output a score.\n"
            "Scale: -1.0 (Extreme Fear/Bad News) to +1.0 (Extreme Greed/Good News).\n"
            "0.0 is Neutral or Irrelevant."
        )

    def analyze_batch(self, headlines: list[str]) -> float:
        """
        Analyzes a batch of headlines and returns a single sentiment score (-1.0 to 1.0).
        """
        if not headlines:
            return 0.0

        if not self.client:
            return 0.0 # Neural/Fallback if no API Key
            
        try:
            headlines_str = "\n".join([f"- {h}" for h in headlines])
            
            user_prompt = (
                f"Analyze these headlines for market sentiment:\n\n{headlines_str}\n\n"
                "Return ONLY the sentiment score (float)."
            )
            
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0, # Deterministic
                max_tokens=10
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parsing logic
            match = re.search(r"[-+]?\d*\.\d+|[-+]?\d+", content)
            if match:
                score = float(match.group())
                return max(min(score, 1.0), -1.0)
            return 0.0
            
        except Exception as e:
            logger.error(f"DeepSeek News Analysis Failed: {e}")
            return 0.0

if __name__ == "__main__":
    # Test
    analyst = DeepSeekNewsAnalyst()
    print(analyst.analyze_batch([
        "Laba Bersih BBRI Tumbuh 10% di Q3",
        "Ekonomi Indonesia Diprediksi Melambat",
        "IHSG Hancur lebur di sesi pertama"
    ]))
