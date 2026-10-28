import assert from 'node:assert/strict';
import {test} from 'node:test';
import {isPublicIPv4,requestAllowed} from '../ci/fixtures/web/public_browser_guard.mjs';
test('deny private and reserved IPs',()=>{
  for(const ip of ['127.0.0.1','10.2.3.4','169.254.169.254','192.168.1.1','172.31.1.1',
    '100.64.0.1','198.51.100.2','203.0.113.2','192.0.2.2','0.0.0.0','::1'])
    assert.equal(isPublicIPv4(ip),false,ip);
  assert.equal(isPublicIPv4('1.1.1.1'),true);
});
test('deny cross-origin, HTTP, POST, file',()=>{
  const o='https://example.com';
  assert.equal(requestAllowed('https://example.com/page',o,'GET'),true);
  for(const [url,m] of [['https://other.com','GET'],['http://example.com','GET'],
    ['https://example.com','POST'],['file:///etc/passwd','GET']])
    assert.equal(requestAllowed(url,o,m),false);
});
