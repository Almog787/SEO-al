import json
import time
import os
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

# Verify API Key
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY is missing!")
    exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

def extract_text_from_html(file_path):
    """Step 1: Extract clean text from HTML"""
    print("🧹 Extracting and cleaning text from HTML...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print(f"❌ File {file_path} not found.")
        exit(1)

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
    """Step 2: Ask AI for exactly 7 keyphrases targeting US & EU"""
    print("🧠 AI is identifying top 7 keyphrases for US & EU markets...")
    prompt = f"""
    Analyze this English text. Your target audience is the United States and Europe.
    Identify the top 7 main SEO entities or keyphrases (1-3 words each) that are most critical for ranking in these global regions.
    
    Return ONLY a valid JSON list of exactly 7 strings, like this:["keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5", "keyword 6", "keyword 7"]
    
    Text: {text}
    """
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

def check_trends_and_longtail(keywords):
    """Step 3: Fetch Trends and Autocomplete for both US and Europe (GB as proxy)"""
    print("🔍 Fetching Google Trends & Autocomplete data for US & Europe...")
    trends_data = {}
    
    # US = United States, GB = Great Britain (Proxy for English searches in Europe)
    target_regions = ['US', 'GB'] 
    
    for kw in keywords:
        print(f"   -> Checking: {kw}")
        long_tail = set()
        score_sum = 0
        valid_regions = 0
        
        for region in target_regions:
            # Google Autocomplete (Long-tail keywords)
            try:
                url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={kw}&hl=en&gl={region.lower()}"
                r = requests.get(url, timeout=5)
                suggestions = r.json()[1][:2] # Top 2 long-tails per region
                for s in suggestions:
                    long_tail.add(s)
            except:
                pass
                
            # Google Trends
            try:
                pytrends = TrendReq(hl='en-US', tz=360, timeout=(5,10))
                pytrends.build_payload([kw], timeframe='today 3-m', geo=region)
                df = pytrends.interest_over_time()
                if not df.empty and kw in df:
                    score_sum += int(df[kw].mean())
                    valid_regions += 1
                time.sleep(3) # Prevent IP ban
            except:
                pass
                
        # Calculate average score across valid regions
        avg_score = (score_sum // valid_regions) if valid_regions > 0 else "Unknown (Blocked by Google)"
        
        trends_data[kw] = {
            "trend_score": avg_score,
            "long_tail": list(long_tail)
        }
        
    return trends_data

def optimize_text_with_ai(original_data, trends_data):
    """Step 4: AI rewrites the content for US & EU markets based on Trends"""
    print("✨ AI is rewriting and optimizing the text based on Global Trends...")
    
    prompt = f"""
    You are an elite SEO Copywriter targeting the United States and European markets.
    The content is in English.
    
    I am providing the original text and REAL search volume data (Trends & Long-tail Autocomplete) gathered from the US and Europe.
    
    Original Title: {original_data['original_title']}
    Original H1: {original_data['original_h1']}
    Original Text (Snippet): {original_data['text'][:3000]}
    
    Real Google Trends Data (Targeting US & EU):
    {json.dumps(trends_data, ensure_ascii=False)}
    
    Your task:
    1. Rewrite the H1 to be highly catchy and SEO-optimized for the US/EU audience.
    2. Write a new Meta Description (up to 155 chars, engaging).
    3. Write a new SEO-optimized introductory paragraph (3-4 sentences) that naturally incorporates the high-volume 'long-tail' keywords from the data.

    Return EXACTLY a JSON in this structure:
    {{
      "optimized_h1": "New Catchy SEO H1",
      "optimized_meta_description": "New Meta Description",
      "optimized_intro_paragraph": "A rewritten, engaging intro...",
      "keywords_used":["kw1", "kw2"],
      "seo_recommendations_for_writer":["tip 1", "tip 2"]
    }}
    """
    
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

def generate_markdown(optimized_result, trends_data):
    """Generate a clean, English Markdown report"""
    md = "# 🌍 Global SEO Text Optimization Report (US & Europe)\n\n"
    
    md += "## 🎯 AI Optimized Content (Ready to Copy-Paste!)\n\n"
    md += f"**Optimized H1:**\n`{optimized_result['optimized_h1']}`\n\n"
    md += f"**Optimized Meta Description:**\n`{optimized_result['optimized_meta_description']}`\n\n"
    md += f"**Optimized Intro Paragraph (Includes Long-Tail Keywords):**\n> {optimized_result['optimized_intro_paragraph']}\n\n"
    
    md += "---\n\n## 📈 Google Trends & Search Data (US & GB/EU)\n\n"
    md += "| Original Keyword | Avg Trend Score | Discovered Long-Tail Queries (US & EU) |\n"
    md += "|---|---|---|\n"
    for kw, data in trends_data.items():
        long_tails = ", ".join(data['long_tail']) if data['long_tail'] else "No data"
        md += f"| **{kw}** | {data['trend_score']} | {long_tails} |\n"

    md += "\n## 💡 SEO Recommendations for the Writer\n"
    for tip in optimized_result.get('seo_recommendations_for_writer',[]):
        md += f"- {tip}\n"
        
    return md

def main():
    html_file = 'input.html'
    
    if not os.path.exists(html_file):
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write("<html><head><title>Test Page</title></head><body><h1>Software Development</h1><p>We build scalable cloud software for businesses. Contact us today.</p></body></html>")
        print("Created a sample input.html file. Please put your real English HTML code there and run again.")
    
    extracted = extract_text_from_html(html_file)
    
    # Get EXACTLY 7 keywords
    base_keywords = get_base_keywords(extracted['text'])
    
    # Check against US and EU data
    trends_data = check_trends_and_longtail(base_keywords)
    
    # Rewrite
    optimization_result = optimize_text_with_ai(extracted, trends_data)
    
    # Save output
    with open('seo_data.json', 'w', encoding='utf-8') as f:
        json.dump({"trends": trends_data, "optimization": optimization_result}, f, ensure_ascii=False, indent=4)
        
    with open('OPTIMIZED_CONTENT.md', 'w', encoding='utf-8') as f:
        f.write(generate_markdown(optimization_result, trends_data))
        
    print("✅ Done! Check OPTIMIZED_CONTENT.md for your new US/EU optimized text.")

if __name__ == "__main__":
    main()
