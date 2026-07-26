import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
print("=== 1. API KEY CHECK ===")
print("Key present in .env:", bool(key))
print("Key prefix:", key[:10] + "..." if key else "None")

print("\n=== 2. DIRECT GEMINI 2.0 FLASH NETWORK TEST ===")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
prompt = """You are an intent extraction engine for an AML Compliance Agent.
Output ONLY a single valid JSON object with the schema:
{
  "intent_type": "aggregation_query",
  "entities": {"amount_threshold": 10000.0},
  "pattern_hint": "structuring"
}
User Query: show me accounts moving money in pieces under 10k"""

payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0}
}

try:
    resp = requests.post(url, json=payload, timeout=15)
    print("HTTP Response Status Code:", resp.status_code)
    if resp.status_code == 200:
        res_json = resp.json()
        text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        print("Raw LLM Response Text returned by Gemini API:")
        print(text)
    else:
        print("HTTP Error Body:", resp.text)
except Exception as e:
        print("Network Call Exception:", str(e))

print("\n=== 3. INVOCATION VIA INTENT_EXTRACTOR ===")
sys.path.insert(0, ".")
from src.agent.intent_extractor import extract_intent
result = extract_intent("show me accounts moving money in pieces under 10k", session_id="live_proof")
print("Extracted Intent Object:", result.model_dump())
