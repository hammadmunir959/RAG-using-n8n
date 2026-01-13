
import scrapy
from bs4 import BeautifulSoup

class UniversalSpider(scrapy.Spider):
    name = "universal"
    
    def __init__(self, start_url=None, allowed_domains=None, max_depth=1, *args, **kwargs):
        super(UniversalSpider, self).__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []
        self.allowed_domains = allowed_domains.split(',') if allowed_domains else []
        self.max_depth = int(max_depth)

    def parse(self, response):
        # Extract title
        title = response.css('title::text').get() or response.url

        # Smart text extraction (using BS4 to kill scripts/styles)
        soup = BeautifulSoup(response.body, 'lxml')
        
        # Kill all script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "meta"]):
            script.extract()
            
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        yield {
            'url': response.url,
            'title': title,
            'text': text[:50000],  # Safety limit
            'depth': response.meta.get('depth', 0)
        }

        # Follow links if depth allows
        current_depth = response.meta.get('depth', 0)
        if current_depth < self.max_depth:
            for href in response.css('a::attr(href)'):
                yield response.follow(href, self.parse)
