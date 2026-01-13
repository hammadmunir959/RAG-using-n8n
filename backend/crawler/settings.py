
# Scrapy settings for crawler project
BOT_NAME = "crawler"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
ITEM_PIPELINES = {
   "crawler.pipelines.IngestPipeline": 300,
}
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
USER_AGENT = 'Mozilla/5.0 (compatible; ResearchBot/1.0; +http://localhost)'
