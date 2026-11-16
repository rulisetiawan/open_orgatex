const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Lenovo Yoga 7i/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('aktif'));
  assert.match(await page.locator('#sourceInfo').textContent(),/A001.*502/);
  await page.locator('summary').filter({hasText:'Edit nilai langkah PRG'}).click();
  await page.locator('#editStep').selectOption('2');
  const raw=page.locator('[data-prg-offset]').first();const offset=Number(await raw.getAttribute('data-prg-offset'));await raw.fill('1.25');await page.locator('#applyStep').click();
  await page.locator('#batchName').fill('TEST-E013-A');await page.locator('#p0').fill('1000');await page.locator('#add').click();
  assert.equal(await page.locator('#count').textContent(),'1 batch');
  await page.locator('#machine').fill('A001');await page.locator('#batchName').fill('TEST-A001-B');await page.locator('#add').click();
  await page.locator('#machine').fill('E013');await page.locator('#batchName').fill('TEST-E013-C');await page.locator('#add').click();
  assert.equal(await page.locator('#count').textContent(),'3 batch');
  await page.locator('[data-edit="0"]').click();await page.locator('#p0').fill('999.5');await page.locator('#add').click();
  assert.equal(await page.locator('#count').textContent(),'3 batch');
  // Reject duplicate references without altering the existing plan.
  await page.locator('#reference').fill('062340');await page.locator('#batchName').fill('DUPLICATE');await page.locator('#add').click();assert.match(await page.locator('#message').textContent(),/Referensi sudah/);
  const draftEvent=page.waitForEvent('download');await page.locator('#save').click();const draft=await draftEvent;const draftPath=path.join(__dirname,'browser-planning.draft.json');await draft.saveAs(draftPath);
  await page.locator('[data-delete="0"]').click();assert.equal(await page.locator('#count').textContent(),'2 batch');await page.locator('#draftFile').setInputFiles(draftPath);await page.waitForFunction(()=>document.getElementById('count').textContent==='3 batch');
  const downloadEvent=page.waitForEvent('download');await page.locator('#export').click();const zip=await downloadEvent;await zip.saveAs(path.join(__dirname,'browser-planning.zip'));
  assert.match(await page.locator('#message').textContent(),/ZIP siap/);
  await page.screenshot({path:path.join(__dirname,'preview_desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({path:path.join(__dirname,'preview_mobile.png'),fullPage:false});
  // File mode must explain the helper requirement, not fail silently.
  await page.goto('file:///D:/File%20HMI/Analisis/Planner_Batch.html');assert.match(await page.locator('#connection').textContent(),/Buka_Planner_Batch.cmd/);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(__dirname,'browser-test-result.json'),JSON.stringify({passed:true,tests:['raw PRG edit','multi-machine planning','batch edit','duplicate rejection','draft roundtrip','ZIP export','mobile overflow','file-mode explanation','no JS errors'],editedPrgOffset:offset},null,2));
  console.log('PASS browser workflow; edited PRG offset '+offset);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
