
import requests
import os

class IngestPipeline:
    def process_item(self, item, spider):
        # Send data to main API for ingestion
        api_url = "http://127.0.0.1:8000/api/internal/ingest"
        
        # We need to handle potential connection errors cleanly
        try:
            requests.post(api_url, json={
                "url": item['url'],
                "title": item['title'],
                "text": item['text']
            }, timeout=10)
        except Exception as e:
            spider.logger.error(f"Failed to ingest item {item['url']}: {e}")
            
        return item
