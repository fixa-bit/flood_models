const path = require('path');
const assert = require('node:assert/strict');
const {chromium} = require(path.join(process.env.TEMP,'flood_portal_browser/node_modules/playwright'));

(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  const page = await browser.newPage({viewport:{width:1450,height:1000}});
  const errors = [];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  try {
    await page.goto('http://127.0.0.1:8787/#rainfall',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>document.querySelector('#rainfall-comparison-plot')?._fullLayout&&document.querySelector('#rainfall-availability-chart')?._fullLayout&&document.querySelectorAll('.rainfall-panel').length===4,{timeout:30000});
    let check=await page.evaluate(()=>({
      visible:!document.querySelector('#rainfall-view').hidden,
      combinedTraces:document.querySelector('#rainfall-comparison-plot').data.map(trace=>({name:trace.name,axis:trace.yaxis,days:trace.x.length})),
      panels:[...document.querySelectorAll('.rainfall-panel h3')].map(node=>node.textContent),
      finalDays:document.querySelectorAll('.rainfall-source-plot')[0].data[0].x.length,
      availabilityRows:document.querySelector('#rainfall-availability-chart').data.length,
      availabilityDays:document.querySelector('#rainfall-availability-chart').data[0].x.length,
      year:document.querySelector('#rainfall-year').value,
      availabilityYear:document.querySelector('#rainfall-availability-year').value,
    }));
    assert.equal(check.visible,true);
    assert.equal(check.panels.length,4);
    assert.equal(check.panels.some(name=>name.includes('IMERG')),false);
    assert.equal(check.panels.some(name=>name.includes('saved long request')),false);
    assert.equal(check.combinedTraces.length,4);
    assert.equal(check.combinedTraces[0].days,366);
    assert.ok(check.combinedTraces.every(trace=>trace.axis==='y'));
    assert.equal(check.finalDays,366);
    assert.equal(check.availabilityRows,1);
    assert.equal(check.availabilityDays,13442);
    assert.equal(check.year,'2024');
    assert.equal(check.availabilityYear,'all');
    await page.locator('#rainfall-view').screenshot({path:path.join(__dirname,'../qa/rainfall-sources-2024.png')});

    await page.selectOption('#rainfall-year','all');
    await page.waitForFunction(()=>document.querySelectorAll('.rainfall-source-plot').length===4&&document.querySelectorAll('.rainfall-source-plot')[0].data?.[0]?.x?.length===13422,{timeout:30000});
    check=await page.evaluate(()=>[...document.querySelectorAll('.rainfall-source-plot')].map(node=>node.data[0].x.length));
    assert.deepEqual(check,[13422,20,3228,10]);
    check=await page.evaluate(()=>document.querySelector('#rainfall-comparison-plot').data.map(trace=>trace.x.length));
    assert.deepEqual(check,[13422,20,3228,10]);

    await page.selectOption('#rainfall-source','chirps_original_samples');
    await page.waitForFunction(()=>document.querySelectorAll('.rainfall-panel').length===1);
    await page.selectOption('#rainfall-availability-year','2024');
    await page.waitForFunction(()=>document.querySelector('#rainfall-availability-chart').data?.[0]?.x?.length===366);
    assert.equal(await page.locator('#rainfall-year').inputValue(),'all');
    assert.equal(await page.locator('#rainfall-source').inputValue(),'chirps_original_samples');
    assert.deepEqual(errors,[]);
    console.log('Rainfall browser smoke: four retained sources, one rainfall scale, full record, independent selectors OK');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
