import json
import time
import os
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
from google import genai
from google.genai import types

# 1. בדיקת מפתח API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY is missing! Make sure it's set in GitHub Secrets.")
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
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print(f"❌ File {file_path} not found.")
        # יצירת קובץ דמה אם המשתמש שכח ליצור אחד
        dummy_html = "<html><head><title>Test</title></head><body><h1>My Website</h1><p>Welcome to our software company. We do cloud computing.</p></body></html>"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(dummy_html)
        html = dummy_html
        print(f"✅ Created a sample {file_path}. Processing the sample...")

    soup = BeautifulSoup(html, 'html.parser')
    original_title = soup.title.string if soup.title else "N/A"
    original_h1 =[h.get_text(strip=True) for h in soup.find_all('h1')]
    
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe']):
        tag.decompose()
        
    main_text = soup.get_text(separator=' ', strip=True)
    return {
        "original_title": original_title,
        "original_h1": original_h1,
        "text": main_text[:20000]
    }

def get_base_keywords(text):
    print(f"🧠 AI ({MODEL_ID}) is identifying top 7 keyphrases for US & EU markets...")
    prompt = f"""
    Analyze this English text. Your target audience is the United States and Europe.
    Identify the top 7 main SEO entities or keyphrases (1-3 words each) that are most critical for ranking in these global regions.
    Return ONLY a valid JSON list of exactly 7 strings.
    Text: {text}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def check_trends_and_longtail(keywords):
    print("🔍 Fetching Google Trends & Autocomplete data for US & EU...")
    trends_data = {}
    target_regions =['US', 'GB'] 
    
    for kw in keywords:
        print(f"   -> Checking: {kw}")
        long_tail = set()
        score_sum = 0
        valid_regions = 0
        
        for region in target_regions:
            # שלב 1: איסוף זנב ארוך מ-Google Autocomplete
            try:
                url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}"
                r = requests.get(url, timeout=5)
                suggestions = r.json()[1][:2]
                for s in suggestions: long_tail.add(s)
            except: pass
                
            # שלב 2: בדיקת נפחי חיפוש מגוגל טרנדס
            try:
                pytrends = TrendReq(hl='en-US', tz=360, timeout=(5,10))
                pytrends.build_payload([kw], timeframe='today 3-m', geo=region)
                df = pytrends.interest_over_time()
                if not df.empty and kw in df:
                    score_sum += int(df[kw].mean())
                    valid_regions += 1
                time.sleep(3) # השהייה למניעת חסימות IP
            except: pass
                
        avg_score = (score_sum // valid_regions) if valid_regions > 0 else "Unknown"
        trends_data[kw] = {"trend_score": avg_score, "long_tail": list(long_tail)}
        
    return trends_data

def optimize_text_with_ai(original_data, trends_data):
    print("✨ AI is rewriting content into HTML layout based on Trends...")
    
    # שימוש ב-{{{{ ו-}}}} עבור התבנית של Liquid כדי שפייתון לא יקרוס בשגיאת f-string
    prompt = f"""
    You are an elite SEO Copywriter and Web Developer targeting the US and EU markets.
    
    Original Content snippet: {original_data['text'][:4000]}
    
    Google Trends & Autocomplete Data (Use the high-volume long-tail keywords!):
    {json.dumps(trends_data, ensure_ascii=False)}
    
    Task 1: Rewrite the article using the EXACT HTML structure provided below.
    Adapt the headings, paragraphs, and lists to fit the original topic, but KEEP the TailwindCSS classes, the YAML frontmatter, the 'lead' paragraph, the highlighted 'bg-blue-50' div, and the Call To Action button at the bottom.
    
    TEMPLATE TO FOLLOW AND ADAPT:
    ---
    layout: post
    title: "Optimized Catchy Title Here"
    description: "Optimized Meta Description Here"
    tag: "Relevant Tag"
    icon: "relevant-icon"
    image: "https://images.unsplash.com/photo-example"
    ---

    <p class="lead text-xl text-slate-600">
        [Engaging, SEO-optimized intro incorporating long-tail keywords]
    </p>

    <h2>1. [First Subheading]</h2>
    <p>[Content...]</p>
    <ul>
        <li>[Point 1]</li>
        <li>[Point 2]</li>
    </ul>

    <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 my-8">
        <h3 class="mt-0 text-primary">[Highlight/Important Point]</h3>
        <p class="mb-0">[Highlight content...]</p>
    </div>

    <h2>[Another Subheading]</h2>
    <p>[More content...]</p>

    <div class="mt-10 text-center not-prose">
        <a href="{{{{ '/your-relevant-link.html' | relative_url }}}}" class="inline-flex items-center gap-2 bg-primary text-white px-8 py-4 rounded-xl font-bold no-underline hover:bg-blue-700 hover:shadow-lg hover:-translate-y-1 transition-all">
            <span class="material-symbols-outlined">arrow_forward</span>[Call to Action Text]
        </a>
    </div>

    Task 2: Create a changelog explaining the SEO changes made.

    Return EXACTLY a JSON in this structure:
    {{
      "html_content": "The full string containing the YAML frontmatter and HTML layout",
      "changelog": {{
         "summary": "Brief explanation of the rewrite strategy",
         "changes_made": ["change 1", "change 2"],
         "seo_reasoning": "Why these changes improve US/EU rankings based on the data"
      }}
    }}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return parse_ai_json_response(response.text)

def generate_changelog_md(optimization_result, trends_data):
    """מייצר את קובץ ה-Markdown המסביר את השינויים שבוצעו"""
    cl = optimization_result['changelog']
    
    md = "# 📈 SEO Optimization Changelog\n\n"
    md += f"**Strategy Summary:** {cl['summary']}\n\n"
    
    md += "## 🛠️ Changes Made to the HTML Layout\n"
    for change in cl['changes_made']:
        md += f"- {change}\n"
        
    md += f"\n## 🧠 SEO Reasoning (US & EU Focus)\n"
    md += f"> {cl['seo_reasoning']}\n\n"
    
    md += "---\n\n## 📊 Data Driven Decisions (Google Trends & Autocomplete)\n"
    md += "The following real-world data was used to restructure the content:\n\n"
    md += "| Keyword | Trend Score | Long-Tail Queries Integrated |\n"
    md += "|---|---|---|\n"
    
    for kw, data in trends_data.items():
        long_tails = ", ".join(data['long_tail']) if data['long_tail'] else "No data"
        md += f"| **{kw}** | {data['trend_score']} | {long_tails} |\n"

    return md

def main():
    html_file = 'input.html'
    
    # 1. חילוץ טקסט
    extracted = extract_text_from_html(html_file)
    
    # 2. זיהוי מילות מפתח על ידי AI
    base_keywords = get_base_keywords(extracted['text'])
    
    # 3. איסוף נתונים אסטרטגיים מגוגל
    trends_data = check_trends_and_longtail(base_keywords)
    
    # 4. שכתוב הקוד על ידי AI לתוך ה-HTML המעוצב
    optimization_result = optimize_text_with_ai(extracted, trends_data)
    
    # 5. שמירת כל הקבצים שגיטהאב ישמור ויעלה בחזרה
    with open('seo_data.json', 'w', encoding='utf-8') as f:
        json.dump(trends_data, f, ensure_ascii=False, indent=4)
        
    with open('OPTIMIZED_ARTICLE.html', 'w', encoding='utf-8') as f:
        f.write(optimization_result['html_content'])
        
    with open('SEO_CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(generate_changelog_md(optimization_result, trends_data))
        
    print("✅ Done! Successfully generated OPTIMIZED_ARTICLE.html and SEO_CHANGELOG.md")

if __name__ == "__main__":
    main()
