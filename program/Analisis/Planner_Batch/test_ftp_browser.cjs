const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Lenovo Yoga 7i/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/api/ftp',async route=>{let body=route.request().postDataJSON();requests.push(body);await route.fulfill({json:{message:body.action==='check'?'Pemeriksaan baca berhasil':'Transfer fixture berhasil',machine:'A001',existing:2,added:1,job:'BROWSER-MOCK',backup:body.action==='send'?'/custom/A001/QUEUE.BTD.backup_test':null}})});
 await p.goto('http://127.0.0.1:8768/');await p.waitForFunction(()=>document.getElementById('connection').textContent.includes('aktif'));
 await p.locator('#machine').fill('A001');await p.locator('#batchName').fill('TEST-FTP');await p.locator('#add').click();
 await p.locator('#ftpHost').fill('example.invalid');await p.locator('#ftpPort').fill('2121');await p.locator('#ftpBatchRoot').fill('/custom/batches');await p.locator('#ftpQueue').fill('/custom/{machine}/QUEUE.BTD');
 await p.locator('#ftpCheck').click();assert.match(await p.locator('#ftpStatus').textContent(),/Belum diisi: Username/);assert.equal(requests.length,0);
 await p.locator('#ftpUser').fill('operator');await p.locator('#ftpPassword').fill('SECRET-FIXTURE');
 assert.equal(await p.locator('#ftpSend').isDisabled(),true);await p.locator('#ftpCheck').click();await p.waitForFunction(()=>document.getElementById('ftpStatus').textContent.includes('Pemeriksaan baca'));
 await p.locator('#ftpPaused').check();await p.locator('#ftpReserved').check();assert.equal(await p.locator('#ftpSend').isEnabled(),true);
 await p.locator('#ftpSend').click();await p.waitForFunction(()=>document.getElementById('ftpStatus').textContent.includes('Transfer fixture'));
 assert.equal(await p.locator('#ftpSend').isDisabled(),true);assert.equal(requests.length,2);assert.equal(requests[1].ftp.port,2121);assert.equal(requests[1].ftp.queuePath,'/custom/{machine}/QUEUE.BTD');assert.equal(requests[1].writersPaused,true);
 const event=p.waitForEvent('download');await p.locator('#save').click();const d=await event;const file=path.join(__dirname,'ftp-browser-draft.json');await d.saveAs(file);assert.equal(fs.readFileSync(file,'utf8').includes('SECRET-FIXTURE'),false);
 await p.locator('#ftpPanel').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(__dirname,'preview_ftp.png')});
 await p.setViewportSize({width:390,height:844});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);assert.deepEqual(errors,[]);
 console.log('PASS FTP manual fields, read-only check, send gates, secret-free draft, responsive UI; FTP requests mocked');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
