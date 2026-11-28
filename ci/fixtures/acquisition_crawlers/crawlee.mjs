import assert from 'node:assert/strict';
import http from 'node:http';
import { CheerioCrawler, Configuration } from 'crawlee';
const base='http://127.0.0.1:18768';
const seen=[];
const pages={'/':'<html><h1>ROOT</h1><a href="/a">A</a><a href="/a#dup">Again</a><a href="/blocked">Blocked</a></html>',
'/a':'<html><h1>CHILD</h1><a href="/">Home</a></html>'};
const server=http.createServer((req,res)=>{
  seen.push(req.url);
  if(req.url==='/robots.txt'){res.writeHead(200,{'Content-Type':'text/plain'});res.end('User-agent: *\nDisallow: /blocked\n');}
  else if(Object.hasOwn(pages,req.url)){res.writeHead(200,{'Content-Type':'text/html'});res.end(pages[req.url]);}
  else{res.writeHead(403);res.end('denied');}
});
await new Promise(resolve=>server.listen(18768,'127.0.0.1',resolve));
const records=[];
try{
  const crawler=new CheerioCrawler({
    maxRequestsPerCrawl:6,maxConcurrency:1,maxRequestRetries:0,
    respectRobotsTxtFile:true,useSessionPool:false,retryOnBlocked:false,
    requestHandlerTimeoutSecs:15,
    async requestHandler({request,$,enqueueLinks}){
      records.push([request.loadedUrl??request.url,$('h1').text()]);
      await enqueueLinks({strategy:'same-origin'});
    }
  },new Configuration({persistStorage:false}));
  await crawler.run([base+'/']);
  assert.deepEqual(records.sort(),[[base+'/','ROOT'],[base+'/a','CHILD']]);
  assert.equal(seen.filter(x=>x==='/a').length,1);
  assert.ok(seen.includes('/robots.txt')&&!seen.includes('/blocked'),JSON.stringify(seen));
  console.log('ZEIBAEL_CRAWLEE='+JSON.stringify({pages:records.length,requests:seen,status:'PASS'}));
}finally{await new Promise(resolve=>server.close(resolve));}
