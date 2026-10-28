/** Execute only public, bounded browser actions on the checked HTTPS origin. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {pinnedPublicIp,requestAllowed} from './public_browser_guard.mjs';
const target=process.env.ZEIBAEL_BROWSER_URL;
const steps=JSON.parse(process.env.ZEIBAEL_BROWSER_STEPS||'[]');
if(!target||!Array.isArray(steps)||steps.length>8||!process.env.ZEIBAEL_OUTPUT_DIR)
  throw Error('Reviewed browser inputs required');
const u=new URL(target);
if(u.protocol!=='https:'||u.search||u.hash||u.username||u.password||!u.hostname.includes('.')||
   !/^[a-z0-9.-]+$/.test(u.hostname)||(u.port&&u.port!=='443'))
  throw Error('Unreviewed URL');
const ip=await pinnedPublicIp(u.hostname);
const browser=await chromium.launch({headless:true,args:[
  '--host-resolver-rules=MAP '+u.hostname+' '+ip+', EXCLUDE localhost',
  '--disable-background-networking']});
try{
  const ctx=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:false,
    serviceWorkers:'block',permissions:[]});
  await ctx.route('**/*',route=>{
    const r=route.request();
    return requestAllowed(r.url(),u.origin,r.method())?route.continue():route.abort();
  });
  await ctx.routeWebSocket('**/*',ws=>ws.close());
  const page=await ctx.newPage();
  page.on('popup',popup=>popup.close());
  const response=await page.goto(target,{waitUntil:'domcontentloaded',timeout:20000});
  assert.ok(response&&response.status()>=200&&response.status()<400,'Public page failed to load');
  const observations=[];
  for(const s of steps){
    if(!s||!['click','fill','text','screenshot'].includes(s.action))throw Error('Invalid action');
    if(s.action==='click')await page.locator(s.selector).click({timeout:5000});
    else if(s.action==='fill')await page.locator(s.selector).fill(s.value,{timeout:5000});
    else if(s.action==='text')observations.push((await page.locator('body').innerText()).slice(0,1500));
    else observations.push('Screenshot requested');
  }
  assert.equal(new URL(page.url()).origin,u.origin);
  const dest=path.join(process.env.ZEIBAEL_OUTPUT_DIR,'files');
  fs.mkdirSync(dest,{recursive:true});
  await page.screenshot({path:path.join(dest,'public-page.png'),timeout:10000});
  assert.ok(fs.statSync(path.join(dest,'public-page.png')).size>1000);
  const summary={schema:1,source:'public',status:'success',url:page.url(),
    title:(await page.title()).slice(0,180),steps_completed:steps.length,
    text:(await page.locator('body').innerText()).slice(0,1500),
    observations,screenshot:'public-page.png'};
  fs.writeFileSync(path.join(dest,'browser-result.json'),JSON.stringify(summary,null,2));
  console.log('ZEIBAEL_PUBLIC_BROWSER_RESULT_JSON='+JSON.stringify(summary));
}finally{await browser.close();}
