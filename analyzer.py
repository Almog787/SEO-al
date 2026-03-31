import json
import time
import os
import google.generativeai as genai
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

# הגדרת ה-API מהסביבה של GitHub Actions
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup(['script', 'style', 'nav', 'footer', 'header']):
        s.decompose()
    return soup.get_text(separator=' ', strip=True)

def analyze_with_gemini(text):
    # שימוש בגרסה 1.5 Pro (החזקה ביותר לניתוח טקסט ארוך)
    # אם תרצה 2.0, פשוט שנה ל-'gemini-2.0-flash-exp' או 'gemini-2.0-pro-exp'
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    prompt = f"""
    Analyze the following Hebrew website content for SEO.
    1. Identify the 8 most important keywords/topics.
    2. Suggest a search intent (Informational/Transactional).
    3. Suggest 3 SEO optimized titles.
    
    Return ONLY a valid JSON:
    {{
      "keywords": [ {{"term": "word", "relevance": 95}}, ... ],
      "intent": "...",
      "titles": ["...", "...", "..."]
    }}

    Text: {text[:40000]}
    """
    
    print("Sending to Gemini 1.5 Pro...")
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

def check_trends(keyword):
    pytrends = TrendReq(hl='iw-IL', tz=-120)
    try:
        pytrends.build_payload([keyword], timeframe='today 3-m', geo='IL')
        df = pytrends.interest_over_time()
        score = int(df[keyword].mean()) if not df.empty else 0
        time.sleep(5) # השהייה ארוכה יותר למניעת חסימה בגיטהאב
        return score
    except:
        return 0

def main():
    if not os.path.exists('input.html'):
        print("input.html missing")
        return

    with open('input.html', 'r', encoding='utf-8') as f:
        content = clean_html(f.read())

    ai_data = analyze_with_gemini(content)
    
    results = []
    for kw in ai_data['keywords']:
        print(f"Checking trend for: {kw['term']}")
        trend_score = check_trends(kw['term'])
        results.append({
            "keyword": kw['term'],
            "relevance": kw['relevance'],
            "trend_score": trend_score,
            "status": "High Opportunity" if trend_score > 30 and kw['relevance'] > 80 else "Check"
        })

    final_output = {
        "strategy": ai_data['intent'],
        "titles": ai_data['titles'],
        "analysis": results
    }

    with open('ai_trends_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
