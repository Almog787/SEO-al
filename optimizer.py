import json
import time
import os
import requests
import warnings
import pandas as pd
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
from google import genai
from google.genai import types

# 1. השתקת אזהרות לניקוי הלוג ב-GitHub
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# 2. בדיקת מפתח API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY is missing!")
    exit(1)

# התחברות ל-SDK החדש (v2)
client = genai.Client(api_key=API_KEY)
MODEL_ID = 'gemini-2.5-flash' 

def parse_ai_json_response(response_text):
    """מנקה ומפענח JSON מה-AI עם טיפול בשגיאות"""
    try:
        raw_text = response_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
        return json.loads(raw_text)
    except Exception as e:
        print(f"❌ JSON Parse Error: {e}")
        return None

def extract_text_from_html(file_path):
    print("🧹 Extracting text from HTML...")
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} not found. Creating dummy content.")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("<html><body><h1>Economic Trends 2024</h1><p>Inflation is rising and central banks are reacting.</p></body></html>")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'svg']):
        tag.decompose()
    return soup.get_text(separator=' ', strip=True)[:20000]

def get_base_keywords(text):
    print(f"🧠 AI is identifying top 7 global keyphrases...")
    prompt = f"""
    Analyze this financial/geopolitical text. Target audience: US and Europe.
    Identify the top 7 most important SEO keyphrases (1-3 words each).
    Return ONLY a valid JSON list of 7 strings.
    Text: {text}
    """
    response = client.models.generate_content(
        model=MODEL_ID, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def check_trends_and_longtail(keywords):
    print("🔍 Fetching Google Trends & Autocomplete for US & EU...")
    trends_data = {}
    target_regions = ['US', 'GB'] 
    for kw in keywords:
        print(f"   -> Checking: {kw}")
        long_tail = set()
        score_sum, valid_regions = 0, 0
        for region in target_regions:
            try:
                url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}"
                r = requests.get(url, timeout=5)
                for s in r.json()[1][:2]: long_tail.add(s)
            except: pass
            try:
                pytrends = TrendReq(hl='en-US', tz=360, timeout=(10,20))
                pytrends.build_payload([kw], timeframe='today 3-m', geo=region)
                df = pytrends.interest_over_time()
                if not df.empty and kw in df:
                    score_sum += int(df[kw].mean())
                    valid_regions += 1
                time.sleep(4) 
            except: pass
        trends_data[kw] = {
            "trend_score": (score_sum // valid_regions) if valid_regions > 0 else "Low",
            "long_tail": list(long_tail)
        }
    return trends_data

def optimize_text_with_ai(original_text, trends_data):
    """שילוב הפרומפט ה'סיפורי' מהקוד שלך עם תבנית ה-HTML המעוצבת"""
    print("✨ AI is rewriting into a Human-First Narrative HTML...")
    
    prompt = f"""
    You are an expert financial and geopolitical analyst (Forbes/WSJ style). 
    Rewrite the original text into a compelling, human-first article.
    
    SEO Data to integrate naturally: {json.dumps(trends_data, ensure_ascii=False)}
    Original Text: {original_text[:4000]}

    REQUIREMENTS:
    1. Human-First: No keyword stuffing. Weave keywords naturally into a story.
    2. Narrative Arc: Start with a relatable problem (e.g. inflation, gas prices), explain the 'Why' (geopolitics), and end with a solution.
    3. EXACT HTML TEMPLATE:
    
    ---
    layout: post
    title: "Catchy Human-Friendly Title"
    description: "Compelling meta description"
    tag: "Geopolitics"
    icon: "public"
    image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1000&q=80"
    ---

    <p class="lead text-xl text-slate-600">[Relatable Hook Paragraph]</p>
    
    <h2>[Benefit-driven heading]</h2>
    <p>[Core concepts in simple language]</p>

    <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 my-8 not-prose">
        <h3 class="mt-0 text-primary font-bold text-xl mb-2">How This Directly Affects You</h3>
        <p class="text-slate-700 mb-0">[The main takeaway for the reader's wallet/life]</p>
    </div>

    <h2>[Final heading leading to action]</h2>
    <p>[Empower the reader with knowledge or tools]</p>

    <div class="mt-10 text-center not-prose">
        <a href="{{{{ '/percentage.html' | relative_url }}}}" class="inline-flex items-center gap-2 bg-primary text-white px-8 py-4 rounded-xl font-bold no-underline hover:bg-blue-700 hover:shadow-lg hover:-translate-y-1 transition-all">
            <span class="material-symbols-outlined">calculate</span>
            Calculate Your Personal Impact
        </a>
    </div>

    Return ONLY JSON: {{"html_content": "...", "changelog": {{"summary": "...", "changes_made": [], "seo_reasoning": "..."}}}}
    """
    response = client.models.generate_content(
        model=MODEL_ID, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def main():
    original_text = extract_text_from_html('input.html')
    keywords = get_base_keywords(original_text)
    trends = check_trends_and_longtail(keywords)
    result = optimize_text_with_ai(original_text, trends)
    
    if result:
        with open('OPTIMIZED_ARTICLE.html', 'w', encoding='utf-8') as f:
            f.write(result['html_content'])
        
        # יצירת ה-Changelog (משולב מהלוגיקה שלך)
        cl = result['changelog']
        md = f"# 📈 SEO Changelog\n\n**Summary:** {cl['summary']}\n\n"
        md += "## Changes Made\n" + "\n".join([f"- {c}" for c in cl['changes_made']])
        md += f"\n\n## Reasoning\n> {cl['seo_reasoning']}\n\n"
        md += "## Data Used\n| Keyword | Trend | Suggestions |\n|---|---|---|\n"
        for k, v in trends.items():
            md += f"| {k} | {v['trend_score']} | {', '.join(v['long_tail'])} |\n"
            
        with open('SEO_CHANGELOG.md', 'w', encoding='utf-8') as f:
            f.write(md)
            
        print("✅ Process Finished Successfully!")

if __name__ == "__main__":
    main()
