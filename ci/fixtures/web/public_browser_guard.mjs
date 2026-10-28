import dns from 'node:dns/promises';
import net from 'node:net';
export function isPublicIPv4(ip) {
  if(net.isIP(ip)!==4) return false;
  const [a,b,c]=ip.split('.').map(Number);
  if(a===0||a===10||a===127||a>=224||(a===100&&b>=64&&b<=127)||
     (a===169&&b===254)||(a===172&&b>=16&&b<=31)||
     (a===192&&(b===168||(b===0&&(c===0||c===2))))||
     (a===198&&(b===18||b===19||(b===51&&c===100)))||
     (a===203&&b===0&&c===113)) return false;
  return true;
}
export async function pinnedPublicIp(hostname) {
  const addresses=await dns.lookup(hostname,{all:true,verbatim:true});
  if(!addresses.length||addresses.some(r=>r.family!==4&&r.family!==6))throw Error('Invalid DNS answer');
  const v4=addresses.filter(r=>r.family===4);
  if(!v4.length||v4.some(r=>!isPublicIPv4(r.address)))throw Error('Private or reserved DNS/IP prohibited');
  if(addresses.some(r=>r.family===6&&!/^[23][0-9a-f]{3}:/i.test(r.address)))throw Error('Non-global IPv6 prohibited');
  return v4[0].address;
}
export function requestAllowed(url,origin,method){
  try{const u=new URL(url);return u.protocol==='https:'&&u.origin===origin&&
      (method==='GET'||method==='HEAD');}catch{return false;}
}
