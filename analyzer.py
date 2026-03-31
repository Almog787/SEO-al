import json
import time
import os
import google.generativeai as genai
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

# ==========================================================
# הגדרות ראשוניות
# ==========================================================
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # <--- הדבק כאן את המפתח שלך
genai.configure(api_key=GEMINI_API_KEY)

def clean_and_extract_text(html_content):
    """מנקה תגיות לא רלוונטיות ומחלץ טקסט נקי בלבד"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for element in soup(['script', 'style', 'footer', 'nav', 'header', 'noscript', 'svg']):
        element.decompose()
    
    body = soup.find('body')
    text = body.get_text(separator=' ', strip=True) if body else soup.get_text(separator=' ', strip=True)
    return text

def analyze_text_with_gemini(text):
    """שולח את הטקסט לג'מיני ומקבל ניתוח סמנטי בפורמט JSON"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert Israeli SEO analyst. Analyze the following webpage text.
    1. Extract the top 7 most important SEO keywords (nouns/phrases).
    2. Group them to roots (lemmatization) in Hebrew.
    3. Identify search intent.
    4. Suggest 3 H1 titles in Hebrew.

    Return ONLY a JSON object with this structure:
    {{
      "keywords": [ {{"word": "מילה", "ai_relevance": 90}}, ... ],
      "search_intent": "...",
      "search_intent_explanation": "...",
      "suggested_titles": ["...", "...", "..."]
    }}

    Text content:
    {text[:30000]}
    """
    
    print("🤖 Gemini מנתח את תוכן האתר...")
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def get_google_trends(keyword):
    """בודק פופולריות ב-Google Trends בישראל"""
    pytrends = TrendReq(hl='iw-IL', tz=-120)
    try:
        pytrends.build_payload([keyword], cat=0, timeframe='today 3-m', geo='IL')
        df = pytrends.interest_over_time()
        
        score = int(df[keyword].mean()) if not df.empty else 0
        
        # מציאת ביטויים עולים
        related = pytrends.related_queries()
        rising = []
        if related and keyword in related and related[keyword]['rising'] is not None:
            rising = related[keyword]['rising']['query'].head(3).tolist()
            
        time.sleep(3) # מניעת חסימה מגוגל
        return {"score": score, "rising_terms": rising}
    except Exception as e:
        print(f"⚠️ שגיאה בטרנדס עבור '{keyword}': {e}")
        return {"score": 0, "rising_terms": []}

def main():
    # קריאת הקלט
    if not os.path.exists('input.html'):
        print("❌ קובץ input.html לא נמצא! אנא צור אותו והדבק בו את קוד ה-HTML.")
        return

    with open('input.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # עיבוד
    clean_text = clean_and_extract_text(html)
    ai_results = analyze_text_with_gemini(clean_text)
    
    final_analysis = {
        "strategic_info": {
            "intent": ai_results['search_intent'],
            "explanation": ai_results['search_intent_explanation'],
            "titles": ai_results['suggested_titles']
        },
        "keywords_trends": []
    }

    print(f"📈 בודק טרנדים עבור {len(ai_results['keywords'])} מילות מפתח...")
    for item in ai_results['keywords']:
        word = item['word']
        print(f"🔍 בודק: {word}")
        trend = get_google_trends(word)
        
        # לוגיקת המלצה
        rec = "Keep"
        if trend['score'] < 10 and item['ai_relevance'] > 80:
            rec = "Replace with a higher volume synonym"
        elif trend['score'] > 40:
            rec = "Strong Keyword - Optimize for this"

        final_analysis["keywords_trends"].append({
            "term": word,
            "relevance_score": item['ai_relevance'],
            "google_search_volume_index": trend['score'],
            "rising_related_topics": trend['rising_terms'],
            "recommendation": rec
        })

    # שמירת הפלט
    with open('ai_trends_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(final_analysis, f, ensure_ascii=False, indent=4)
    
    print("\n✅ הניתוח הושלם בהצלחה!")
    print("📁 הפלט מחכה לך בקובץ: ai_trends_analysis.json")

if __name__ == "__main__":
    main()
