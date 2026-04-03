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

# השתקת אזהרות עתידיות כדי לנקות את הלוג
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# 1. בדיקת מפתח API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY environment variable is not set!")
    exit(1)

# התחברות ל-SDK של גוגל
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"❌ Error configuring Google AI client: {e}")
    exit(1)

def parse_ai_json_response(response_text):
    """מנגנון הגנה: מנקה טקסט במקרה שה-AI החזיר סימוני קוד (Markdown)"""
    try:
        raw_text = response_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}")
        print(f"   Raw AI Response was: {response_text}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred while parsing JSON: {e}")
        return None

def extract_text_from_html(file_path):
    """מוציא טקסט נקי מקובץ HTML"""
    print("🧹 Extracting and cleaning text from HTML...")
    if not os.path.exists(file_path):
        print(f"⚠️ File '{file_path}' not found. Please create it.")
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    # הסרת אלמנטים לא רלוונטיים
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe']):
        tag.decompose()
        
    main_text = soup.get_text(separator=' ', strip=True)
    return {"text": main_text[:20000]} # מגביל את הטקסט למניעת חריגה

def get_base_keywords(text):
    """מזהה מילות מפתח בסיסיות בעזרת AI"""
    print(f"🧠 AI is identifying top 7 keyphrases...")
    prompt = f"""
    Analyze the following English text from a financial/geopolitical blog. 
    Your target audience is from the US and Europe.
    Identify the top 7 most important SEO keyphrases (1-3 words each).
    Return ONLY a valid JSON list of these 7 strings.

    Text: "{text}"
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return parse_ai_json_response(response.text)
    except Exception as e:
        print(f"❌ Error getting keywords from AI: {e}")
        return []

def check_trends_and_longtail(keywords):
    """בודק טרנדים בגוגל ומציע מילות מפתח ארוכות-זנב"""
    print("🔍 Fetching Google Trends & Autocomplete data...")
    trends_data = {}
    target_regions = ['US', 'GB'] 
    
    for kw in keywords:
        print(f"   -> Checking keyword: '{kw}'")
        long_tail = set()
        score_sum = 0
        valid_regions = 0
        
        # איסוף הצעות השלמה אוטומטית מגוגל
        for region in target_regions:
            try:
                url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}"
                r = requests.get(url, timeout=5)
                r.raise_for_status()
                suggestions = r.json()[1][:2] # לוקח את 2 ההצעות הראשונות
                for s in suggestions: long_tail.add(s)
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Could not fetch suggestions for '{kw}' in {region}: {e}")
                
        # בדיקת פופולריות ב-Google Trends
        try:
            pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 20))
            pytrends.build_payload([kw], timeframe='today 3-m', geo='') # חיפוש עולמי
            df = pytrends.interest_over_time()
            if not df.empty and kw in df and not df[kw].isnull().all():
                avg_score = int(df[kw].mean())
            else:
                avg_score = "Low"
            time.sleep(2) # המתנה קצרה כדי לא לחסום את ה-IP
        except Exception as e:
            print(f"   ⚠️ Could not fetch trends for '{kw}': {e}")
            avg_score = "Unknown"
                
        trends_data[kw] = {"trend_score": avg_score, "long_tail": list(long_tail)}
        
    return trends_data

def optimize_text_with_ai(original_data, trends_data):
    """משכתב את המאמר לפורמט HTML סופי עם הנחיות לכתיבה איכותית"""
    print("✨ AI is rewriting the article into an engaging narrative HTML...")
    prompt = f"""
    You are an expert financial and geopolitical analyst who writes engaging, human-first articles for a popular blog.
    Your tone is clear, authoritative, and helpful, like an article in Forbes or The Wall Street Journal, but written for the average person.
    
    You have the following SEO data:
    High-Volume Keywords: {json.dumps(trends_data, ensure_ascii=False)}

    Here is the original, raw text: 
    Original Text: "{original_data['text'][:4000]}"

    Your Task:
    Rewrite the raw text into a compelling, story-driven article using the provided HTML template.
    1.  **Human-First:** Write for a person, not a search engine. Weave the high-volume keywords naturally into the narrative. DO NOT bold them or stuff them.
    2.  **Narrative Arc:** Create a clear story. Start with a problem the reader feels (e.g., "rising gas prices"), explain the 'why' (geopolitics), and end with a solution (using our site's tools).
    3.  **Title & Description:** Write a catchy, human-readable title and meta description. The title should spark curiosity.
    4.  **Call to Action:** The final button is critical. It must be relevant to the article's topic. For example, if the article is about inflation, the button should point to the Percentage Calculator.
    5.  **Use the EXACT template below.**

    HTML TEMPLATE:
    ---
    layout: post
    title: "A Catchy and Human-Friendly Title"
    description: "A compelling meta description that makes the reader want to click, summarizing the core issue."
    tag: "Geopolitics"
    icon: "public"
    image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1000&q=80"
    ---

    <p class="lead text-xl text-slate-600">[Start with a powerful, relatable introductory paragraph that hooks the reader.]</p>
    
    <h2>[A clear, benefit-driven heading]</h2>
    <p>[Explain the core concepts here. Weave in the long-tail keywords naturally. Use simple language.]</p>
    
    <h2>[Another compelling heading explaining the 'Why']</h2>
    <p>[Continue the narrative, connecting the global events to the reader's personal life.]</p>

    <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 my-8 not-prose">
        <h3 class="mt-0 text-primary font-bold text-xl mb-2">How This Directly Affects You</h3>
        <p class="text-slate-700 mb-0">[Summarize the main takeaway for the reader's wallet, e.g., how it impacts their gas prices or savings.]</p>
    </div>

    <h2>[A final heading leading to the solution]</h2>
    <p>[Explain how the reader can take action or empower themselves with knowledge.]</p>

    <div class="mt-10 text-center not-prose">
        <a href="{{{{ '/percentage.html' | relative_url }}}}" class="inline-flex items-center gap-2 bg-primary text-white px-8 py-4 rounded-xl font-bold no-underline hover:bg-blue-700 hover:shadow-lg hover:-translate-y-1 transition-all">
            <span class="material-symbols-outlined">calculate</span>
            Calculate Your Personal Inflation Rate
        </a>
    </div>

    Return ONLY a valid JSON object with the keys "html_content" and "changelog".
    The "changelog" should explain why the new version is better for human readers and SEO.
    Example: {{"html_content": "...", "changelog": {{"summary": "Transformed a keyword-stuffed text into an engaging narrative.", "changes_made": ["Rewrote the title for clarity.", "Structured the article with a clear story.", "Integrated keywords naturally."], "seo_reasoning": "Google's E-E-A-T algorithm rewards high-quality, helpful content. This version builds trust and provides real value, leading to better rankings and user engagement than simple keyword stuffing."}}}}
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return parse_ai_json_response(response.text)
    except Exception as e:
        print(f"❌ Error getting optimized content from AI: {e}")
        return None

def generate_changelog_md(optimization_result, trends_data):
    """יוצר קובץ Markdown עם סיכום השינויים והנתונים"""
    cl = optimization_result.get('changelog', {})
    summary = cl.get('summary', 'No summary provided.')
    changes_made = cl.get('changes_made', [])
    seo_reasoning = cl.get('seo_reasoning', 'No reasoning provided.')
    
    md = f"# 📈 SEO Optimization Changelog\n\n**Summary:** {summary}\n\n"
    md += "## 🛠️ Changes Made\n"
    if changes_made:
        for change in changes_made: md += f"- {change}\n"
    else:
        md += "- No specific changes listed.\n"
        
    md += f"\n## 🧠 SEO Reasoning\n> {seo_reasoning}\n\n"
    md += "## 📊 Data Used for Optimization\n| Keyword | Avg. Trend Score (3-mo) | Long-Tail Suggestions |\n|---|---|---|\n"
    for kw, data in trends_data.items():
        md += f"| {kw} | {data['trend_score']} | {', '.join(data['long_tail'])} |\n"
    return md

def main():
    """התהליך הראשי של הסקריפט"""
    input_file = 'input.html'
    
    print("--- Starting SEO Optimization Process ---")
    
    extracted = extract_text_from_html(input_file)
    if not extracted: return
    
    base_keywords = get_base_keywords(extracted['text'])
    if not base_keywords: 
        print("Could not get keywords. Exiting.")
        return
        
    trends_data = check_trends_and_longtail(base_keywords)
    optimization_result = optimize_text_with_ai(extracted, trends_data)
    
    if not optimization_result:
        print("Could not get optimization result. Exiting.")
        return

    # יצירת קבצי הפלט
    output_dir = 'optimized_output'
    os.makedirs(output_dir, exist_ok=True)
    
    article_path = os.path.join(output_dir, 'OPTIMIZED_ARTICLE.html')
    changelog_path = os.path.join(output_dir, 'SEO_CHANGELOG.md')
    data_path = os.path.join(output_dir, 'seo_data.json')
    
    with open(article_path, 'w', encoding='utf-8') as f:
        f.write(optimization_result.get('html_content', ''))
        
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(generate_changelog_md(optimization_result, trends_data))
        
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(trends_data, f, ensure_ascii=False, indent=4)
        
    print("\n--- Process Finished Successfully! ---")
    print(f"✅ Optimized Article: {article_path}")
    print(f"✅ SEO Changelog: {changelog_path}")
    print(f"✅ SEO Data: {data_path}")

if __name__ == "__main__":
    main()
