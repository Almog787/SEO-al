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

# השתקת אזהרות עתידיות של Pandas ו-Pytrends כדי לנקות את הלוג ב-GitHub
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# 1. בדיקת מפתח API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY is missing!")
    exit(1)

# התחברות ל-SDK החדש של גוגל
client = genai.Client(api_key=API_KEY)
MODEL_ID = 'gemini-2.5-flash' 

def parse_ai_json_response(response_text):
    """מנגנון הגנה: מנקה טקסט במקרה שה-AI החזיר סימוני קוד (Markdown)"""
    raw_text = response_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:-3].strip()
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:-3].strip()
    return json.loads(raw_text)

def extract_text_from_html(file_path):
    print("🧹 Extracting and cleaning text from HTML...")
    if not os.path.exists(file_path):
        print(f"⚠️ File {file_path} not found. Creating dummy content...")
        dummy_html = "<html><body><h1>Tech Solutions</h1><p>We provide cloud computing and AI services.</p></body></html>"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(dummy_html)
        html = dummy_html
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    original_title = soup.title.string if soup.title else "N/A"
    original_h1 = [h.get_text(strip=True) for h in soup.find_all('h1')]
    
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe']):
        tag.decompose()
        
    main_text = soup.get_text(separator=' ', strip=True)
    return {
        "original_title": original_title,
        "original_h1": original_h1,
        "text": main_text[:20000]
    }

def get_base_keywords(text):
    print(f"🧠 AI ({MODEL_ID}) is identifying top 7 keyphrases...")
    prompt = f"""
    Analyze this English text. Your target audience is the US and Europe.
    Identify the top 7 main SEO keyphrases (1-3 words each).
    Return ONLY a valid JSON list of 7 strings.
    Text: {text}
    """
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def check_trends_and_longtail(keywords):
    print("🔍 Fetching Google Trends & Autocomplete data...")
    trends_data = {}
    target_regions = ['US', 'GB'] 
    
    for kw in keywords:
        print(f"   -> Checking: {kw}")
        long_tail = set()
        score_sum = 0
        valid_regions = 0
        
        for region in target_regions:
            try:
                url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}"
                r = requests.get(url, timeout=5)
                suggestions = r.json()[1][:2]
                for s in suggestions: long_tail.add(s)
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
                
        avg_score = (score_sum // valid_regions) if valid_regions > 0 else "Unknown"
        trends_data[kw] = {"trend_score": avg_score, "long_tail": list(long_tail)}
        
    return trends_data

def optimize_text_with_ai(original_data, trends_data):
    print("✨ AI is rewriting content into HTML template...")
    prompt = f"""
    You are an elite SEO Copywriter for US/EU markets.
    
    Data: {json.dumps(trends_data, ensure_ascii=False)}
    Original: {original_data['text'][:4000]}
    
    Task: Rewrite the article into the exact HTML template provided below. 
    Use the high-volume long-tail keywords from the data.

    TEMPLATE:
    ---
    layout: post
    title: "Optimized Catchy Title"
    description: "Meta Description"
    tag: "SEO"
    icon: "trending_up"
    image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1000&q=80"
    ---

    <p class="lead text-xl text-slate-600">[SEO Intro]</p>
    <h2>1. Key Benefit</h2>
    <p>[Body content]</p>
    <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 my-8">
        <h3 class="mt-0 text-primary">Pro Tip</h3>
        <p class="mb-0">[Pro tip content]</p>
    </div>
    <div class="mt-10 text-center not-prose">
        <a href="{{{{ '/contact.html' | relative_url }}}}" class="inline-flex items-center gap-2 bg-primary text-white px-8 py-4 rounded-xl font-bold no-underline transition-all">Get Started</a>
    </div>

    Return ONLY a JSON: {{"html_content": "...", "changelog": {{"summary": "...", "changes_made": [], "seo_reasoning": "..."}}}}
    """
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def generate_changelog_md(optimization_result, trends_data):
    cl = optimization_result['changelog']
    md = f"# 📈 SEO Optimization Changelog\n\n**Summary:** {cl['summary']}\n\n"
    md += "## 🛠️ Changes\n"
    for change in cl['changes_made']: md += f"- {change}\n"
    md += f"\n## 🧠 Reasoning\n> {cl['seo_reasoning']}\n\n"
    md += "## 📊 Data Used\n| Keyword | Trend | Long-Tail |\n|---|---|---|\n"
    for kw, data in trends_data.items():
        md += f"| {kw} | {data['trend_score']} | {', '.join(data['long_tail'])} |\n"
    return md

def main():
    html_file = 'input.html'
    extracted = extract_text_from_html(html_file)
    base_keywords = get_base_keywords(extracted['text'])
    trends_data = check_trends_and_longtail(base_keywords)
    optimization_result = optimize_text_with_ai(extracted, trends_data)
    
    os.makedirs('public', exist_ok=True) # וודא שתיקיית פלט קיימת
    
    with open('seo_data.json', 'w', encoding='utf-8') as f:
        json.dump(trends_data, f, ensure_ascii=False, indent=4)
    with open('OPTIMIZED_ARTICLE.html', 'w', encoding='utf-8') as f:
        f.write(optimization_result['html_content'])
    with open('SEO_CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(generate_changelog_md(optimization_result, trends_data))
        
    print("✅ Done! Files generated successfully.")

if __name__ == "__main__":
    main()
