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

# 1. השתקת אזהרות
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# 2. API Setup
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY missing!")
    exit(1)

client = genai.Client(api_key=API_KEY)
MODEL_ID = 'gemini-2.5-flash' 

def parse_ai_json_response(response_text):
    try:
        raw_text = response_text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"): raw_text = raw_text[3:-3].strip()
        return json.loads(raw_text)
    except: return None

def extract_text_from_html(file_path):
    print("🧹 Extracting text...")
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("<html><body><h1>Global Economy</h1><p>Markets are shifting rapidly.</p></body></html>")
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']): tag.decompose()
    return soup.get_text(separator=' ', strip=True)[:20000]

def get_base_keywords(text):
    print("🧠 Identifying keywords...")
    prompt = f"Analyze this financial text. Identify top 7 SEO keyphrases (1-3 words). Return ONLY JSON list of 7 strings. Text: {text}"
    response = client.models.generate_content(
        model=MODEL_ID, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def check_trends_and_longtail(keywords):
    print("🔍 Fetching data (US & EU)...")
    trends_data = {}
    for kw in keywords:
        print(f"   -> {kw}")
        long_tail, score_sum, valid_regions = set(), 0, 0
        for region in ['US', 'GB']:
            try:
                r = requests.get(f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}", timeout=5)
                for s in r.json()[1][:2]: long_tail.add(s)
            except: pass
            try:
                pytrends = TrendReq(hl='en-US', tz=360, timeout=(10,20))
                pytrends.build_payload([kw], timeframe='today 3-m', geo=region)
                df = pytrends.interest_over_time()
                if not df.empty:
                    score_sum += int(df[kw].mean()); valid_regions += 1
                time.sleep(4)
            except: pass
        trends_data[kw] = {"trend_score": (score_sum // valid_regions) if valid_regions > 0 else "Low", "long_tail": list(long_tail)}
    return trends_data

def optimize_text_with_ai(original_text, trends_data):
    print("✨ Rewriting into Narrative HTML...")
    prompt = f"""
    Expert financial analyst (Forbes style). Rewrite this text into a Human-First story.
    SEO Data: {json.dumps(trends_data, ensure_ascii=False)}
    Original: {original_text[:4000]}
    
    Use this exact HTML layout:
    ---
    layout: post
    title: "Catchy Human Title"
    description: "Compelling meta"
    tag: "Geopolitics"
    icon: "public"
    image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1000&q=80"
    ---
    <p class="lead text-xl text-slate-600">[Hook]</p>
    <h2>[Benefit Heading]</h2>
    <p>[Body]</p>
    <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 my-8 not-prose">
        <h3 class="mt-0 text-primary font-bold text-xl mb-2">How This Affects You</h3>
        <p class="text-slate-700 mb-0">[Takeaway]</p>
    </div>
    <div class="mt-10 text-center not-prose">
        <a href="{{{{ '/percentage.html' | relative_url }}}}" class="bg-primary text-white px-8 py-4 rounded-xl font-bold no-underline">Calculate Personal Impact</a>
    </div>

    Return JSON: {{"html_content": "...", "changelog": {{"summary": "...", "changes_made": [], "seo_reasoning": "..."}}}}
    """
    response = client.models.generate_content(
        model=MODEL_ID, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def main():
    original = extract_text_from_html('input.html')
    keywords = get_base_keywords(original)
    if not keywords: return
    trends = check_trends_and_longtail(keywords)
    result = optimize_text_with_ai(original, trends)
    
    if result:
        # 1. שמירת HTML
        with open('OPTIMIZED_ARTICLE.html', 'w', encoding='utf-8') as f:
            f.write(result['html_content'])
        
        # 2. שמירת ה-JSON שגיטהאב חיפש (השורש שחסרה!)
        with open('seo_data.json', 'w', encoding='utf-8') as f:
            json.dump(trends, f, ensure_ascii=False, indent=4)
        
        # 3. יצירת ה-Changelog
        cl = result['changelog']
        md = f"# 📈 SEO Changelog\n\n**Summary:** {cl['summary']}\n\n"
        md += "## Changes\n" + "\n".join([f"- {c}" for c in cl['changes_made']])
        md += f"\n\n## Reasoning\n> {cl['seo_reasoning']}\n\n"
        md += "## Data Used\n| Keyword | Trend | Suggestions |\n|---|---|---|\n"
        for k, v in trends.items():
            md += f"| {k} | {v['trend_score']} | {', '.join(v['long_tail'])} |\n"
            
        with open('SEO_CHANGELOG.md', 'w', encoding='utf-8') as f:
            f.write(md)
            
        print("✅ Success! All files created in root.")

if __name__ == "__main__":
    main()
