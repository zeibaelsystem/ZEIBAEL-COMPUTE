"""Finite loopback-only crawler comparison; no input URLs or cloud credentials."""
import asyncio
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

BASE="http://127.0.0.1:18767"
SEEN=[]
PAGES={"/":b'<html><body><h1>ZEIBAEL-ROOT</h1><a href="/a">A</a><a href="/a#dup">Again</a><a href="/blocked">Blocked</a></body></html>',
       "/a":b'<html><body><h1>ZEIBAEL-CHILD</h1><a href="/">Home</a></body></html>',
       "/dynamic":b'<html><body><h1 id="result">pending</h1><script>document.getElementById("result").textContent="ZEIBAEL-DYNAMIC"</script></body></html>'}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN.append(self.path)
        if self.path=="/robots.txt":
            body,kind,status=b"User-agent: *\nDisallow: /blocked\n","text/plain",200
        elif self.path in PAGES:
            body,kind,status=PAGES[self.path],"text/html",200
        else:
            body,kind,status=b"denied","text/plain",403
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*_): pass

def scrapy_test():
    import scrapy
    from scrapy.crawler import CrawlerProcess
    from scrapy import signals
    records=[]
    class LocalSpider(scrapy.Spider):
        name="zeibael_fixture"
        start_urls=[BASE+"/"]
        def parse(self,response):
            records.append((response.url,response.css("h1::text").get()))
            for link in response.css("a::attr(href)").getall():
                target=response.urljoin(link)
                u=urlsplit(target)
                if (u.scheme,u.netloc)==("http","127.0.0.1:18767"):
                    yield scrapy.Request(target,callback=self.parse)
    process=CrawlerProcess(settings={"ROBOTSTXT_OBEY":True,"CONCURRENT_REQUESTS":1,
        "CLOSESPIDER_PAGECOUNT":6,"DEPTH_LIMIT":3,"DOWNLOAD_DELAY":0.1,
        "REDIRECT_ENABLED":False,"RETRY_ENABLED":False,"COOKIES_ENABLED":False,
        "TELNETCONSOLE_ENABLED":False,"LOG_LEVEL":"ERROR","DOWNLOAD_TIMEOUT":10,
        "USER_AGENT":"ZEIBAEL-LocalFixture/1.0"})
    process.crawl(LocalSpider)
    process.start()
    assert set(records)=={(BASE+"/","ZEIBAEL-ROOT"),(BASE+"/a","ZEIBAEL-CHILD")},records
    assert SEEN.count("/a")==1 and "/robots.txt" in SEEN and "/blocked" not in SEEN,SEEN
    print("ZEIBAEL_SCRAPY_CRAWL="+json.dumps({"pages":len(records),"requests":SEEN,"status":"PASS"}),flush=True)

async def crawl4ai_test():
    from crawl4ai import AsyncWebCrawler,BrowserConfig,CrawlerRunConfig,CacheMode
    cfg=BrowserConfig(headless=True,verbose=False)
    run=CrawlerRunConfig(cache_mode=CacheMode.BYPASS,wait_for="css:#result",
                         check_robots_txt=True,page_timeout=20000)
    async with AsyncWebCrawler(config=cfg) as crawler:
        result=await crawler.arun(url=BASE+"/dynamic",config=run)
        assert result.success,result.error_message
        assert "ZEIBAEL-DYNAMIC" in str(result.markdown),str(result.markdown)
    assert "/dynamic" in SEEN,SEEN
    print("ZEIBAEL_CRAWL4AI="+json.dumps({"rendered":True,"requests":SEEN,"status":"PASS"}),flush=True)

if __name__=="__main__":
    mode=sys.argv[1]
    with ThreadingHTTPServer(("127.0.0.1",18767),Handler) as server:
        th=threading.Thread(target=server.serve_forever,daemon=True)
        th.start()
        try:
            if mode=="scrapy": scrapy_test()
            elif mode=="crawl4ai": asyncio.run(crawl4ai_test())
            else: raise ValueError("Unknown fixture")
        finally:
            server.shutdown()
            th.join()
