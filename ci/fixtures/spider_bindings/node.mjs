import {Website} from '@spider-rs/spider-rs';
const w=new Website('http://127.0.0.1:18776/');
w.withRespectRobotsTxt(true).withBudget({'*':8}).withDepth(3).withDelay(100).withSubdomains(false).build();
await w.crawl();
console.log(JSON.stringify(w.getLinks()));
