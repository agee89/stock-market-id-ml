# Dokumentasi Integrasi DeepSeek API dengan Python

## Daftar Isi
1. [Pendahuluan](#pendahuluan)
2. [Persiapan Awal](#persiapan-awal)
3. [Instalasi Dependencies](#instalasi-dependencies)
4. [Konfigurasi API](#konfigurasi-api)
5. [Model yang Tersedia](#model-yang-tersedia)
6. [Penggunaan Dasar](#penggunaan-dasar)
7. [Streaming Response](#streaming-response)
8. [Multi-round Conversation](#multi-round-conversation)
9. [Function Calling](#function-calling)
10. [JSON Mode](#json-mode)
11. [Parameter & Konfigurasi](#parameter--konfigurasi)
12. [Error Handling](#error-handling)
13. [Best Practices](#best-practices)
14. [Contoh Kasus Penggunaan](#contoh-kasus-penggunaan)

---

## Pendahuluan

DeepSeek API menyediakan akses ke model AI canggih yang kompatibel dengan format API OpenAI. Ini memungkinkan Anda untuk mengintegrasikan kemampuan AI DeepSeek ke dalam aplikasi Python dengan mudah.

### Fitur Utama
- ✅ Kompatibel dengan OpenAI SDK
- ✅ Mendukung mode streaming dan non-streaming
- ✅ Function calling untuk integrasi tool
- ✅ JSON mode untuk output terstruktur
- ✅ Context caching untuk efisiensi biaya
- ✅ Thinking mode untuk reasoning kompleks

---

## Persiapan Awal

### 1. Dapatkan API Key

1. Kunjungi [DeepSeek Platform](https://platform.deepseek.com/api_keys)
2. Login atau daftar akun baru
3. Buat API key baru
4. Simpan API key dengan aman

⚠️ **Penting**: Jangan pernah membagikan API key Anda atau commit ke repository publik.

### 2. Informasi Endpoint

| Parameter | Value |
|-----------|-------|
| Base URL | `https://api.deepseek.com` |
| Alternative URL | `https://api.deepseek.com/v1` |
| API Key | Dari DeepSeek Platform |

> **Catatan**: `/v1` dalam URL tidak berhubungan dengan versi model.

---

## Instalasi Dependencies

### Instalasi OpenAI SDK

```bash
pip install openai
```

### Instalasi untuk Requirements Tambahan

```bash
# Untuk environment management
pip install python-dotenv

# Untuk async operations (opsional)
pip install aiohttp

# Untuk retry mechanism (opsional)
pip install tenacity
```

### Requirements File

Buat file `requirements.txt`:

```txt
openai>=1.0.0
python-dotenv>=1.0.0
```

Install dengan:

```bash
pip install -r requirements.txt
```

---

## Konfigurasi API

### Metode 1: Environment Variables (Recommended)

Buat file `.env`:

```env
DEEPSEEK_API_KEY=your-api-key-here
```

Kode Python:

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
```

### Metode 2: Direct Configuration

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://api.deepseek.com"
)
```

---

## Model yang Tersedia

### DeepSeek-Chat (V3.2)

Model generalis untuk berbagai tugas:

```python
model="deepseek-chat"
```

**Karakteristik:**
- Non-thinking mode
- Cepat dan efisien
- Cocok untuk chat umum, coding, analisis

**Pricing:**
- Input: $0.27 per 1M tokens
- Output: $1.10 per 1M tokens

### DeepSeek-Reasoner (R1)

Model dengan kemampuan reasoning:

```python
model="deepseek-reasoner"
```

**Karakteristik:**
- Thinking mode aktif
- Reasoning mendalam
- Cocok untuk problem solving kompleks

**Pricing:**
- Input: $0.55 per 1M tokens
- Cache hit: $0.14 per 1M tokens
- Reasoning: $2.19 per 1M tokens
- Output: $2.19 per 1M tokens

---

## Penggunaan Dasar

### Chat Completion Sederhana

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello! Siapa kamu?"}
    ],
    stream=False
)

print(response.choices[0].message.content)
```

### Dengan System Prompt

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "system", 
            "content": "Kamu adalah asisten AI yang ahli dalam pemrograman Python."
        },
        {
            "role": "user", 
            "content": "Jelaskan tentang list comprehension"
        }
    ]
)

print(response.choices[0].message.content)
```

### Menggunakan DeepSeek-Reasoner

```python
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {
            "role": "user",
            "content": "Selesaikan: Jika x + 2y = 10 dan 2x - y = 5, berapakah nilai x dan y?"
        }
    ]
)

# Akses reasoning process
if hasattr(response.choices[0].message, 'reasoning_content'):
    print("Reasoning:", response.choices[0].message.reasoning_content)

print("Answer:", response.choices[0].message.content)
```

---

## Streaming Response

### Basic Streaming

```python
def stream_chat(prompt):
    stream = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()

# Penggunaan
stream_chat("Ceritakan tentang Python dalam 3 paragraf")
```

### Streaming dengan Error Handling

```python
def safe_stream_chat(prompt):
    try:
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            timeout=30
        )
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content
        
        print()
        return full_response
        
    except Exception as e:
        print(f"\nError during streaming: {e}")
        return None

# Penggunaan
response = safe_stream_chat("Apa itu machine learning?")
```

---

## Multi-round Conversation

### Implementasi Conversation History

```python
class ChatSession:
    def __init__(self, client, system_prompt=None):
        self.client = client
        self.messages = []
        
        if system_prompt:
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })
    
    def send_message(self, user_message, stream=False):
        # Tambahkan pesan user
        self.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Dapatkan response
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=self.messages,
            stream=stream
        )
        
        if stream:
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_response += content
            print()
            assistant_message = full_response
        else:
            assistant_message = response.choices[0].message.content
            print(assistant_message)
        
        # Simpan response assistant
        self.messages.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    
    def get_history(self):
        return self.messages
    
    def clear_history(self, keep_system=True):
        if keep_system and self.messages and self.messages[0]["role"] == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []

# Penggunaan
session = ChatSession(
    client, 
    system_prompt="Kamu adalah asisten coding yang membantu."
)

session.send_message("Halo! Aku ingin belajar Python")
session.send_message("Bagaimana cara membuat fungsi?")
session.send_message("Bisa berikan contohnya?")

# Lihat history
print("\n--- Chat History ---")
for msg in session.get_history():
    print(f"{msg['role'].upper()}: {msg['content'][:100]}...")
```

---

## Function Calling

### Definisi Function/Tool

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Mendapatkan informasi cuaca untuk lokasi tertentu",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Nama kota dan negara, contoh: Jakarta, Indonesia"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Unit suhu"
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Melakukan operasi matematika",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"]
                    },
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["operation", "a", "b"]
            }
        }
    }
]
```

### Implementasi Function Calling

```python
import json

# Fungsi aktual
def get_weather(location, unit="celsius"):
    # Simulasi API call
    return {
        "location": location,
        "temperature": 28 if unit == "celsius" else 82,
        "unit": unit,
        "condition": "Cerah"
    }

def calculate(operation, a, b):
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "Error: Division by zero"
    }
    return {"result": operations.get(operation)}

# Function dispatcher
available_functions = {
    "get_weather": get_weather,
    "calculate": calculate
}

def run_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    
    # Request pertama dengan tools
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    
    # Jika model ingin memanggil function
    if tool_calls:
        messages.append(response_message)
        
        # Execute setiap function call
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"Calling {function_name} with args: {function_args}")
            
            # Panggil fungsi yang sesuai
            function_to_call = available_functions[function_name]
            function_response = function_to_call(**function_args)
            
            # Tambahkan hasil ke messages
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(function_response)
            })
        
        # Request kedua dengan hasil function
        second_response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        
        return second_response.choices[0].message.content
    
    return response_message.content

# Penggunaan
print(run_conversation("Bagaimana cuaca di Jakarta?"))
print(run_conversation("Hitung 15 kali 24"))
print(run_conversation("Berapa 100 dibagi 4?"))
```

---

## JSON Mode

### Response Format JSON

```python
from pydantic import BaseModel
from typing import List

# Definisi schema dengan Pydantic
class CodeExample(BaseModel):
    language: str
    code: str
    explanation: str

class TutorialResponse(BaseModel):
    title: str
    description: str
    examples: List[CodeExample]

# Request dengan JSON mode
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant that responds in JSON format."
        },
        {
            "role": "user",
            "content": """Buat tutorial singkat tentang list comprehension di Python. 
            Berikan dalam format JSON dengan struktur:
            {
                "title": "string",
                "description": "string",
                "examples": [
                    {
                        "language": "string",
                        "code": "string",
                        "explanation": "string"
                    }
                ]
            }"""
        }
    ],
    response_format={"type": "json_object"}
)

# Parse response
import json
result = json.loads(response.choices[0].message.content)
print(json.dumps(result, indent=2, ensure_ascii=False))
```

### Structured Output dengan Instructor

```bash
pip install instructor
```

```python
import instructor
from pydantic import BaseModel, Field
from typing import List

# Patch OpenAI client dengan Instructor
client = instructor.from_openai(
    OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )
)

# Definisi model
class Person(BaseModel):
    name: str = Field(description="Nama lengkap")
    age: int = Field(description="Usia dalam tahun")
    occupation: str = Field(description="Pekerjaan")
    skills: List[str] = Field(description="Keahlian yang dimiliki")

# Extract structured data
person = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "user",
            "content": """
            Budi adalah seorang software engineer berusia 28 tahun. 
            Dia ahli dalam Python, JavaScript, dan Docker.
            """
        }
    ],
    response_model=Person
)

print(f"Nama: {person.name}")
print(f"Usia: {person.age}")
print(f"Pekerjaan: {person.occupation}")
print(f"Keahlian: {', '.join(person.skills)}")
```

---

## Parameter & Konfigurasi

### Temperature

Mengontrol keacakan output (0.0 - 2.0):

```python
# Deterministik (konsisten)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Jelaskan fotosintesis"}],
    temperature=0.0
)

# Balanced (default)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Tulis cerita pendek"}],
    temperature=1.0
)

# Kreatif
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Buat puisi tentang AI"}],
    temperature=1.5
)
```

### Max Tokens

Membatasi panjang response:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Jelaskan Python"}],
    max_tokens=150  # Maksimal 150 tokens
)
```

### Top P (Nucleus Sampling)

Alternatif untuk temperature:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Generate ide startup"}],
    top_p=0.9  # Menggunakan 90% probabilitas tertinggi
)
```

### Frequency & Presence Penalty

Mengurangi repetisi:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Tulis artikel panjang tentang AI"}],
    frequency_penalty=0.5,  # Kurangi kata yang sering muncul
    presence_penalty=0.5    # Dorong topik baru
)
```

### Stop Sequences

Hentikan generasi pada kata tertentu:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Ceritakan dongeng"}],
    stop=["THE END", "---"]
)
```

### Kombinasi Parameter Optimal

```python
# Untuk coding
coding_response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Buat fungsi Python untuk quicksort"}],
    temperature=0.2,
    max_tokens=500,
    top_p=0.9
)

# Untuk creative writing
creative_response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Tulis cerita sci-fi"}],
    temperature=1.3,
    max_tokens=1000,
    presence_penalty=0.6,
    frequency_penalty=0.3
)

# Untuk analisis faktual
analysis_response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Analisis data ekonomi"}],
    temperature=0.3,
    max_tokens=800,
    top_p=0.95
)
```

---

## Error Handling

### Comprehensive Error Handler

```python
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
import time

class DeepSeekClient:
    def __init__(self, api_key, max_retries=3):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.max_retries = max_retries
    
    def chat(self, messages, model="deepseek-chat", **kwargs):
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                return response
                
            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Rate limit hit. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception("Rate limit exceeded after retries")
            
            except APIConnectionError as e:
                if attempt < self.max_retries - 1:
                    print(f"Connection error. Retrying...")
                    time.sleep(1)
                else:
                    raise Exception("Connection failed after retries")
            
            except APIError as e:
                print(f"API Error: {e}")
                raise
            
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise
    
    def safe_chat(self, messages, default_response="Maaf, terjadi kesalahan.", **kwargs):
        try:
            response = self.chat(messages, **kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error: {e}")
            return default_response

# Penggunaan
client = DeepSeekClient(api_key=os.environ.get("DEEPSEEK_API_KEY"))

response = client.safe_chat(
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response)
```

### Timeout Handling

```python
from openai import OpenAI
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Request timeout")

def chat_with_timeout(client, messages, timeout_seconds=30):
    # Set alarm
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        signal.alarm(0)  # Cancel alarm
        return response.choices[0].message.content
    except TimeoutError:
        print(f"Request timeout after {timeout_seconds} seconds")
        return None
    finally:
        signal.alarm(0)  # Ensure alarm is canceled

# Penggunaan
response = chat_with_timeout(
    client,
    [{"role": "user", "content": "Complex question"}],
    timeout_seconds=30
)
```

---

## Best Practices

### 1. API Key Security

```python
# ✅ GOOD: Gunakan environment variables
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("DEEPSEEK_API_KEY")

# ❌ BAD: Hardcode API key
api_key = "sk-xxxxxxx"  # Jangan lakukan ini!
```

### 2. Efficient Token Usage

```python
def count_tokens(text):
    """Estimasi jumlah tokens (1 token ≈ 4 karakter)"""
    return len(text) // 4

def optimize_prompt(prompt, max_tokens=1000):
    """Potong prompt jika terlalu panjang"""
    estimated_tokens = count_tokens(prompt)
    if estimated_tokens > max_tokens:
        # Potong dengan perbandingan 4:1
        max_chars = max_tokens * 4
        return prompt[:max_chars] + "..."
    return prompt

# Penggunaan
long_prompt = "..." * 1000  # Prompt sangat panjang
optimized = optimize_prompt(long_prompt, max_tokens=500)
```

### 3. Context Caching

Untuk conversation panjang, gunakan context caching:

```python
# Tandai pesan yang ingin di-cache
messages = [
    {
        "role": "system",
        "content": "Long system prompt...",
        "cache_control": {"type": "ephemeral"}  # Cache this
    },
    {
        "role": "user",
        "content": "Question"
    }
]

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages
)
```

### 4. Rate Limiting

```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            now = time.time()
            
            # Hapus calls yang sudah expired
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()
            
            # Check rate limit
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    print(f"Rate limit: waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            
            self.calls.append(time.time())
            return func(*args, **kwargs)
        
        return wrapper

# Limit ke 10 calls per menit
@RateLimiter(max_calls=10, period=60)
def call_api(prompt):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Penggunaan
for i in range(15):
    result = call_api(f"Question {i+1}")
    print(f"Response {i+1}: {result[:50]}...")
```

### 5. Async Operations

```python
import asyncio
from openai import AsyncOpenAI

async_client = AsyncOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

async def async_chat(prompt):
    response = await async_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

async def batch_process(prompts):
    tasks = [async_chat(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    return results

# Penggunaan
prompts = [
    "Apa itu Python?",
    "Jelaskan machine learning",
    "Apa itu blockchain?"
]

results = asyncio.run(batch_process(prompts))
for i, result in enumerate(results):
    print(f"Result {i+1}: {result[:100]}...")
```

---

## Contoh Kasus Penggunaan

### 1. Code Generator

```python
class CodeGenerator:
    def __init__(self, client):
        self.client = client
    
    def generate_code(self, description, language="python"):
        prompt = f"""Generate {language} code for: {description}
        
        Requirements:
        - Include comments
        - Follow best practices
        - Include example usage
        
        Return only the code without explanation."""
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert {language} programmer."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def explain_code(self, code):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a code explainer."},
                {"role": "user", "content": f"Explain this code:\n\n{code}"}
            ],
            temperature=0.5
        )
        
        return response.choices[0].message.content
    
    def review_code(self, code):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a code reviewer. Provide constructive feedback."
                },
                {
                    "role": "user",
                    "content": f"Review this code:\n\n{code}"
                }
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content

# Penggunaan
generator = CodeGenerator(client)

# Generate
code = generator.generate_code("binary search algorithm")
print("Generated Code:")
print(code)

# Explain
explanation = generator.explain_code(code)
print("\nExplanation:")
print(explanation)

# Review
review = generator.review_code(code)
print("\nReview:")
print(review)
```

### 2. Document Analyzer

```python
class DocumentAnalyzer:
    def __init__(self, client):
        self.client = client
    
    def summarize(self, text, max_words=100):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": f"""Summarize the following text in max {max_words} words:
                    
                    {text}"""
                }
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        return response.choices[0].message.content
    
    def extract_key_points(self, text):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": f"""Extract key points from this text as a bullet list:
                    
                    {text}"""
                }
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def translate(self, text, target_language="Indonesian"):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": f"Translate to {target_language}:\n\n{text}"
                }
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content

# Penggunaan
analyzer = DocumentAnalyzer(client)

document = """
Artificial Intelligence (AI) is transforming industries worldwide. 
Machine learning algorithms can now process vast amounts of data 
and make predictions with remarkable accuracy. Deep learning, a subset 
of AI, has enabled breakthroughs in image recognition, natural language 
processing, and autonomous systems.
"""

print("Summary:")
print(analyzer.summarize(document))

print("\nKey Points:")
print(analyzer.extract_key_points(document))

print("\nTranslation:")
print(analyzer.translate(document))
```

### 3. Chatbot dengan Memory

```python
import json
from datetime import datetime

class IntelligentChatbot:
    def __init__(self, client, name="Assistant"):
        self.client = client
        self.name = name
        self.conversation_history = []
        self.user_profile = {}
        
        self.system_prompt = f"""You are {name}, a helpful and friendly AI assistant.
        Remember context from previous messages and personalize responses based on user information."""
    
    def chat(self, user_message, stream=False):
        # Tambahkan message ke history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Build messages untuk API
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Tambahkan context dari user profile
        if self.user_profile:
            context = f"User context: {json.dumps(self.user_profile)}"
            messages.append({"role": "system", "content": context})
        
        # Tambahkan history (last 10 messages untuk efisiensi)
        for msg in self.conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Get response
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=stream
        )
        
        if stream:
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_response += content
            print()
            assistant_message = full_response
        else:
            assistant_message = response.choices[0].message.content
        
        # Simpan response
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        return assistant_message
    
    def update_profile(self, key, value):
        """Update informasi user"""
        self.user_profile[key] = value
    
    def save_conversation(self, filename):
        """Simpan conversation ke file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "profile": self.user_profile,
                "history": self.conversation_history
            }, f, indent=2, ensure_ascii=False)
    
    def load_conversation(self, filename):
        """Load conversation dari file"""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.user_profile = data.get("profile", {})
            self.conversation_history = data.get("history", [])

# Penggunaan
bot = IntelligentChatbot(client, name="DeepBot")

# Update profile
bot.update_profile("name", "Budi")
bot.update_profile("interest", "programming")

# Conversation
bot.chat("Halo! Nama saya Budi")
bot.chat("Saya tertarik belajar Python")
bot.chat("Bisa rekomendasikan resources untuk pemula?")

# Save conversation
bot.save_conversation("chat_history.json")
```

### 4. Data Extraction dan Analysis

```python
from typing import List, Dict
import json

class DataExtractor:
    def __init__(self, client):
        self.client = client
    
    def extract_entities(self, text):
        """Extract named entities dari text"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "Extract entities and return as JSON with keys: people, organizations, locations, dates."
                },
                {
                    "role": "user",
                    "content": f"Extract entities from:\n\n{text}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)
    
    def sentiment_analysis(self, text):
        """Analisis sentiment"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": """Analyze sentiment and return JSON:
                    {
                        "sentiment": "positive/negative/neutral",
                        "score": 0.0-1.0,
                        "explanation": "brief explanation"
                    }"""
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        return json.loads(response.choices[0].message.content)
    
    def categorize(self, text, categories: List[str]):
        """Kategorisasi text"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": f"""Categorize this text into one of: {', '.join(categories)}
                    
                    Text: {text}
                    
                    Return JSON: {{"category": "...", "confidence": 0.0-1.0}}"""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(response.choices[0].message.content)

# Penggunaan
extractor = DataExtractor(client)

text = """
Apple Inc. announced yesterday that Tim Cook will visit Jakarta, Indonesia 
next month to meet with local developers. The event will be held on January 15, 2025.
"""

# Entity extraction
entities = extractor.extract_entities(text)
print("Entities:", json.dumps(entities, indent=2))

# Sentiment analysis
review = "Produk ini luar biasa! Sangat puas dengan kualitas dan layanannya."
sentiment = extractor.sentiment_analysis(review)
print("\nSentiment:", json.dumps(sentiment, indent=2))

# Categorization
article = "Python adalah bahasa pemrograman yang populer untuk data science..."
category = extractor.categorize(article, ["Technology", "Business", "Sports", "Health"])
print("\nCategory:", json.dumps(category, indent=2))
```

### 5. Educational Assistant

```python
class TutorBot:
    def __init__(self, client):
        self.client = client
        self.difficulty_level = "beginner"
    
    def set_difficulty(self, level):
        """Set difficulty: beginner, intermediate, advanced"""
        self.difficulty_level = level
    
    def explain_concept(self, concept, subject="programming"):
        """Jelaskan konsep dengan level yang sesuai"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a patient tutor teaching {subject} 
                    at {self.difficulty_level} level. Use clear explanations 
                    and relevant examples."""
                },
                {
                    "role": "user",
                    "content": f"Explain: {concept}"
                }
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    def create_quiz(self, topic, num_questions=5):
        """Generate quiz questions"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": f"Create {num_questions} multiple choice questions about {topic} at {self.difficulty_level} level."
                },
                {
                    "role": "user",
                    "content": f"""Generate quiz in JSON format:
                    {{
                        "questions": [
                            {{
                                "question": "...",
                                "options": ["A", "B", "C", "D"],
                                "correct": "A",
                                "explanation": "..."
                            }}
                        ]
                    }}"""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.8
        )
        
        return json.loads(response.choices[0].message.content)
    
    def check_answer(self, question, user_answer):
        """Check dan berikan feedback"""
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": f"""Question: {question}
                    User's answer: {user_answer}
                    
                    Provide feedback: is it correct? If not, what's the right answer and why?"""
                }
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content

# Penggunaan
tutor = TutorBot(client)
tutor.set_difficulty("beginner")

# Explain concept
explanation = tutor.explain_concept("recursion", "programming")
print("Explanation:")
print(explanation)

# Generate quiz
quiz = tutor.create_quiz("Python basics", num_questions=3)
print("\nQuiz:")
print(json.dumps(quiz, indent=2, ensure_ascii=False))

# Check answer
feedback = tutor.check_answer(
    "What is a list in Python?",
    "A list is a collection of items"
)
print("\nFeedback:")
print(feedback)
```

---

## Performance Optimization

### 1. Response Caching

```python
import hashlib
import json
from functools import lru_cache

class CachedDeepSeekClient:
    def __init__(self, client):
        self.client = client
        self.cache = {}
    
    def _generate_cache_key(self, messages, model, **kwargs):
        """Generate unique cache key"""
        cache_data = {
            "messages": messages,
            "model": model,
            **kwargs
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def chat(self, messages, model="deepseek-chat", use_cache=True, **kwargs):
        """Chat with caching support"""
        if use_cache:
            cache_key = self._generate_cache_key(messages, model, **kwargs)
            
            if cache_key in self.cache:
                print("✓ Cache hit!")
                return self.cache[cache_key]
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        
        result = response.choices[0].message.content
        
        if use_cache:
            self.cache[cache_key] = result
        
        return result
    
    def clear_cache(self):
        """Clear all cache"""
        self.cache.clear()

# Penggunaan
cached_client = CachedDeepSeekClient(client)

# First call - akan hit API
response1 = cached_client.chat([{"role": "user", "content": "Hello"}])

# Second call - dari cache
response2 = cached_client.chat([{"role": "user", "content": "Hello"}])
```

### 2. Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_chat(prompts, client, max_workers=5):
    """Process multiple prompts in parallel"""
    def process_prompt(prompt):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            return {
                "prompt": prompt,
                "response": response.choices[0].message.content,
                "success": True
            }
        except Exception as e:
            return {
                "prompt": prompt,
                "error": str(e),
                "success": False
            }
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_prompt, p): p for p in prompts}
        
        for future in as_completed(futures):
            results.append(future.result())
    
    return results

# Penggunaan
prompts = [
    "Apa itu Python?",
    "Jelaskan OOP",
    "Apa itu API?",
    "Jelaskan REST",
    "Apa itu JSON?"
]

results = batch_chat(prompts, client, max_workers=3)

for result in results:
    if result["success"]:
        print(f"Q: {result['prompt']}")
        print(f"A: {result['response'][:100]}...\n")
    else:
        print(f"Error for '{result['prompt']}': {result['error']}\n")
```

---

## Testing

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch

class TestDeepSeekIntegration(unittest.TestCase):
    def setUp(self):
        self.client = OpenAI(
            api_key="test-key",
            base_url="https://api.deepseek.com"
        )
    
    @patch('openai.OpenAI.chat.completions.create')
    def test_simple_chat(self, mock_create):
        # Mock response
        mock_response = Mock()
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_create.return_value = mock_response
        
        # Test
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        self.assertEqual(
            response.choices[0].message.content,
            "Hello! How can I help you?"
        )
    
    @patch('openai.OpenAI.chat.completions.create')
    def test_streaming(self, mock_create):
        # Mock streaming response
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Hello"))]),
            Mock(choices=[Mock(delta=Mock(content=" World"))]),
        ]
        mock_create.return_value = iter(mock_chunks)
        
        # Test streaming
        stream = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Hi"}],
            stream=True
        )
        
        result = "".join([
            chunk.choices[0].delta.content 
            for chunk in stream
        ])
        
        self.assertEqual(result, "Hello World")

if __name__ == '__main__':
    unittest.run()
```

---

## Monitoring & Logging

```python
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deepseek_api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('DeepSeekAPI')

class MonitoredClient:
    def __init__(self, client):
        self.client = client
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0
        }
    
    def chat(self, messages, **kwargs):
        start_time = datetime.now()
        self.stats["total_requests"] += 1
        
        try:
            logger.info(f"Request started - Messages: {len(messages)}")
            
            response = self.client.chat.completions.create(
                messages=messages,
                **kwargs
            )
            
            # Track tokens
            if hasattr(response, 'usage'):
                tokens = response.usage.total_tokens
                self.stats["total_tokens"] += tokens
                logger.info(f"Tokens used: {tokens}")
            
            duration = (datetime.now() - start_time).total_seconds()
            self.stats["successful_requests"] += 1
            
            logger.info(f"Request completed in {duration:.2f}s")
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Request failed: {str(e)}")
            raise
    
    def get_stats(self):
        return self.stats.copy()

# Penggunaan
monitored = MonitoredClient(client)

response = monitored.chat([
    {"role": "user", "content": "Hello"}
])

print("\nStats:", monitored.get_stats())
```

---

## Troubleshooting

### Common Issues

**1. Authentication Error**
```python
# Error: Invalid API key
# Solution: Verify API key
try:
    response = client.chat.completions.create(...)
except Exception as e:
    if "authentication" in str(e).lower():
        print("Check your API key!")
```

**2. Rate Limit**
```python
# Implement exponential backoff
import time

def api_call_with_backoff(func, max_retries=5):
    for i in range(max_retries):
        try:
            return func()
        except RateLimitError:
            if i < max_retries - 1:
                wait = 2 ** i
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
```

**3. Timeout**
```python
# Set appropriate timeout
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[...],
    timeout=60  # 60 seconds
)
```

---

## Resources

### Official Links
- 📚 [DeepSeek API Documentation](https://api-docs.deepseek.com/)
- 🔑 [Get API Key](https://platform.deepseek.com/api_keys)
- 📊 [API Status](https://status.deepseek.com/)
- 💬 [Discord Community](https://discord.gg/Tc7c45Zzu5)

### Code Examples
- [GitHub Integrations](https://github.com/deepseek-ai/awesome-deepseek-integration)
- [OpenAI Python SDK](https://github.com/openai/openai-python)

### Support
- 📧 Email: api-service@deepseek.com
- 🐦 Twitter: [@deepseek_ai](https://twitter.com/deepseek_ai)

---

## Changelog

### Version 1.0 (December 2024)
- ✅ Dokumentasi lengkap API DeepSeek
- ✅ Contoh kode Python komprehensif
- ✅ Best practices dan optimization
- ✅ Error handling dan monitoring
- ✅ Real-world use cases

---

## Lisensi

Dokumentasi ini dibuat untuk tujuan edukasi. Untuk penggunaan API DeepSeek, silakan lihat [Terms of Service](https://platform.deepseek.com/terms) resmi.

---

**Happy Coding! 🚀**