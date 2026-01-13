
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

def test_ddg():
    query = "latest news gaza"
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    # We use User-Agent to avoid immediate block, though ScrapingAnt usually handles this.
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print(f"Fetching {url}...")
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        print("Failed to fetch")
        return

    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Try to find results
    results = soup.select(".result")
    print(f"Found {len(results)} results")
    
    for res in results[:3]:
        title_tag = res.select_one(".result__title .result__a")
        snippet_tag = res.select_one(".result__snippet")
        
        if title_tag:
            title = title_tag.get_text(strip=True)
            href = title_tag['href']
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else "No snippet"
            print(f"---\nTitle: {title}\nURL: {href}\nSnippet: {snippet[:50]}...")

if __name__ == "__main__":
    test_ddg()
