'use strict';
const path=require('path');
const assert=require('node:assert/strict');
const {chromium}=require(path.join(process.env.TEMP,'flood_portal_browser/node_modules/playwright'));

(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1500,height:1100}});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto('http://127.0.0.1:8787/#summary');
    await page.waitForFunction(()=>document.querySelector('#summary-chart')?.data?.length>0);
    assert.ok(['not_collected','in_progress'].includes(await page.getAttribute('#summary-gee-status','data-state')));
    assert.match(await page.locator('#summary-gee-status').innerText(),/not collected yet|collection has started/);
    assert.equal(await page.evaluate(()=>document.querySelector('#summary-chart').data.some(trace=>/ERA5-Land|PERSIANN|IMERG V07 Final|CHIRPS v2 Daily/.test(trace.name))),false);
    // Browser-only fixture: never written to the real portal snapshot or datasets.
    await page.route('**/data/portal.json*',async route=>{
      const response=await route.fetch();
      const snapshot=await response.json();
      const definitions=[['era5land','ERA5-Land'],['chirps','CHIRPS v2 Daily'],['persiann','PERSIANN-CDR'],['imerg','IMERG V07 Final']];
      snapshot.marala.gee_precipitation={state:'ready',message:'Browser fixture: checked extraction loaded.',method:'Area-weighted UTC days'};
      snapshot.marala.rainfall_sources.push(...definitions.map(([id,name])=>({id:'gee_'+id,name,group:'Earth Engine',status:'test fixture',method:'test fixture',
        rows:[{date:'2024-01-01',value:0},{date:'2024-01-02',value:null},{date:'2024-01-03',value:2}],records:3,values:2,first_date:'2024-01-01',last_date:'2024-01-03'})));
      await route.fulfill({response,json:snapshot});
    });
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#summary-gee-status')?.dataset.state==='ready'&&document.querySelector('#summary-chart')?.data?.some(trace=>trace.name==='ERA5-Land'));
    const traces=await page.evaluate(()=>document.querySelector('#summary-chart').data.filter(trace=>['ERA5-Land','CHIRPS v2 Daily','PERSIANN-CDR','IMERG V07 Final'].includes(trace.name)).map(trace=>({name:trace.name,y:trace.y,axis:trace.yaxis,connectgaps:trace.connectgaps})));
    assert.equal(traces.length,4);
    for(const trace of traces){assert.deepEqual(trace.y,[0,null,2]);assert.equal(trace.axis,'y3');assert.equal(trace.connectgaps,false);}
    assert.deepEqual(errors,[]);
    console.log('PASS: missing-data status; four Earth Engine traces on shared mm/day axis; zeros and gaps preserved; no browser errors.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
