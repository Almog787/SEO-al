import json
import time
import os
import google.generativeai as genai
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

# הגדרת ה-API מהסביבה של GitHub Actions
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY is missing.")
    exit(1)

genai.configure(api_key=API_KEY)

def extract_structured_seo_text(html):
    """מחלץ טקסט עם חשיבות היררכית ל-SEO"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # הסרת רעש
    for s in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg', 'iframe']):
        s.decompose()

    # איסוף נתונים קריטיים ל-SEO
    page_title = soup.title.string if soup.title else "No Title"
    h1s = [h.get_text() for h in soup.find_all('h1')]
    main_text = soup.get_text(separator=' ', strip=True)

    structured_content = f"""
    Original Title: {page_title}
    Main Headings (H1): {", ".join(h1s)}
    Full Body Content: {main_text[:35000]}
    """
    return structured_content

def analyze_with_gemini(text):
    """ניתוח סמנטי עמוק עם Gemini 1.5 Pro"""
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    You are an expert Israeli SEO Analyst. Analyze the following content:
    1. Identify 8 high-impact keywords (focus on nouns and meaningful phrases in Hebrew).
    2. Determine search intent (Transactional, Informational, Commercial).
    3. Provide 3 optimized H1/Title suggestions in Hebrew.
    4. For each keyword, estimate a 'Global Trend Score' (0-100) based on your knowledge of the Israeli market.

    You MUST return a valid JSON object in this format:
    {{
      "keywords": [
         {{"term": "מילה1", "relevance": 95, "estimated_trend": 80}},
         ...
      ],
      "intent": "Search Intent",
      "titles": ["כותרת 1", "כותרת 2", "כותרת 3"]
    }}

    Text:
    {text}
    """
    
    print("🤖 Gemini 1.5 Pro is analyzing content...")
    # הגדרת JSON Mode כדי למנוע טעויות בפורמט
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def check_google_trends(keyword, ai_estimated_score):
    """ניסיון למשוך נתונים מגוגל טרנדס עם הגנה מחסימות"""
    try:
        print(f"🔍 Fetching real-time trend for: {keyword}")
        pytrends = TrendReq(hl='iw-IL', tz=-120, timeout=(10, 25))
        pytrends.build_payload([keyword], timeframe='today 3-m', geo='IL')
        df = pytrends.interest_over_time()
        
        if not df.empty and keyword in df:
            actual_score = int(df[keyword].mean())
            return actual_score if actual_score > 0 else ai_estimated_score
        return ai_estimated_score
    except Exception as e:
        print(f"⚠️ Google Trends blocked/failed for '{keyword}'. Using AI estimated score ({ai_estimated_score}).")
        return ai_estimated_score

def main():
    input_file = 'input.html'
    if not os.path.exists(input_file):
        print(f"❌ {input_file} not found. Please upload it to the repo.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 1. חילוץ טקסט חכם
    structured_text = extract_structured_seo_text(html_content)

    # 2. ניתוח AI
    ai_data = analyze_with_gemini(structured_text)
    
    # 3. הצלבת נתונים עם Google Trends
    final_analysis = []
    for kw in ai_data.get('keywords', []):
        term = kw['term']
        actual_trend = check_google_trends(term, kw['estimated_trend'])
        
        final_analysis.append({
            "keyword": term,
            "relevance": kw['relevance'],
            "trend_score": actual_trend,
            "opportunity_level": "🔥 High" if actual_trend > 40 and kw['relevance'] > 85 else "Medium"
        })
        time.sleep(4) # השהייה בין בקשות טרנדס

    # 4. הכנת פלט סופי
    output = {
        "summary": {
            "intent": ai_data.get('intent'),
            "analysis_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "suggested_titles": ai_data.get('titles')
        },
        "detailed_keywords": final_analysis
    }

    # שמירה
    os.makedirs('public', exist_ok=True)
    with open('public/ai_trends_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print("✅ Full SEO Analysis complete. File saved to public/ai_trends_analysis.json")

if __name__ == "__main__":
    main()
