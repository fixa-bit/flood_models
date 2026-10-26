const path=require('path');
const fs=require('fs');
const assert=require('node:assert/strict');
const {chromium}=require(path.join(process.env.TEMP,'flood_portal_browser/node_modules/playwright'));

(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:1100}});
  const errors=[],report={};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  const changeYear=async(prefix,year)=>{
    await page.selectOption(`#${prefix}-year`,String(year));
    await page.waitForFunction(({prefix,year})=>{
      const graph=document.querySelector(`#${prefix}-chart`),field=document.querySelector(`#${prefix}-year`);
      return !field.disabled&&field.value===String(year)&&graph.layout.uirevision.endsWith('-'+year);
    },{prefix,year});
  };
  const feature=()=>page.evaluate(()=>{
    const graph=document.querySelector('#summary-chart');
    return {year:document.querySelector('#summary-year').value,
      dates:graph.data.map(trace=>trace.x),rain:graph.data.find(trace=>trace.type==='bar').x.length,
      ranges:Array.from({length:6},(_,index)=>graph._fullLayout['xaxis'+(index?index+1:'')].range),
      counts:graph.data.map(trace=>trace.x.length),
      scroll:document.querySelector('#summary-chart-viewport').scrollLeft};
  });
  const availability=()=>page.evaluate(()=>{
    const graph=document.querySelector('#availability-chart'),heat=graph.data[0];
    return {year:document.querySelector('#availability-year').value,days:heat.x.length,
      first:heat.x[0],last:heat.x.at(-1),present:heat.z.map(row=>row.filter(Boolean).length),
      scroll:document.querySelector('#availability-viewport').scrollLeft};
  });
  try{
    await page.goto('http://127.0.0.1:8787/?check=years#summary',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('#availability-chart').data?.length===2);
    assert.equal((await feature()).year,'2024');assert.equal((await availability()).year,'all');
    await changeYear('summary',2025);
    const main2025=await feature();assert.equal(main2025.rain,365);
    assert.ok(main2025.dates.flat().every(day=>day.startsWith('2025-')));
    assert.equal((await availability()).days,20568);
    await changeYear('availability',2018);
    assert.deepEqual((await availability()).present,[365,0,365,0,0,0]);
    assert.deepEqual(await feature(),main2025);
    await page.locator('#availability-scroll').evaluate(slider=>{slider.value=400;slider.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>document.querySelector('#availability-viewport').scrollLeft===400);
    const independent=await availability();
    for(const year of [2016,2026,1970,1971]){
      await changeYear('summary',year);
      const chart=await feature();
      assert.ok(chart.dates.flat().every(day=>day.startsWith(year+'-')));
      for(const range of chart.ranges){assert.equal(range[0].slice(0,10),year+'-01-01');assert.equal(range[1].slice(0,10),year+'-12-31');}
      if(year===2016){assert.equal(chart.rain,306);assert.equal(chart.counts[0],306);}
      if(year===2026){assert.deepEqual(chart.counts.slice(7,9),[8,8]);assert.equal(chart.rain,295);}
      if(year===1970)assert.ok(chart.counts.at(-1)>0);
      assert.deepEqual(await availability(),independent);
      report[year]=chart.counts;
    }
    // A feature-year change clears a date lock; an availability-year change preserves it.
    await changeYear('summary',2024);
    await page.click('#summary-fit-year');
    await page.locator('#summary-chart').evaluate(async graph=>{
      window.scrollTo({top:scrollY+graph.getBoundingClientRect().top-100,behavior:'instant'});
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    });
    const point=await page.locator('#summary-chart').evaluate(graph=>{
      const bounds=graph.getBoundingClientRect(),layout=graph._fullLayout;
      return {x:bounds.left+layout.xaxis._offset+layout.xaxis.d2p('2024-09-22'),y:bounds.top+layout.yaxis._offset+40};
    });
    await page.mouse.move(point.x,point.y);await page.mouse.dblclick(point.x,point.y);
    await page.waitForFunction(()=>document.querySelector('#summary-lock-date').getAttribute('aria-pressed')==='true');
    const locked=await page.locator('#summary-selected-date').innerText();
    await changeYear('availability',2024);
    assert.equal((await availability()).days,366);
    assert.deepEqual((await availability()).present,[354,120,366,0,0,0]);
    assert.equal(await page.locator('#summary-selected-date').innerText(),locked);
    assert.equal(await page.locator('#summary-lock-date').getAttribute('aria-pressed'),'true');
    const lockedFeature=await feature();
    await changeYear('availability',2026);
    const latest=await availability();assert.equal(latest.days,365);assert.equal(latest.last,'2026-12-31');
    assert.deepEqual(await feature(),lockedFeature);
    await changeYear('availability','all');assert.equal((await availability()).days,20568);
    await changeYear('summary',2025);
    assert.ok(await page.locator('#summary-date-cursor').isHidden());
    assert.equal(await page.locator('#summary-lock-date').getAttribute('aria-pressed'),'false');
    // Both year controls remain usable on a narrow screen.
    await page.setViewportSize({width:390,height:844});
    await changeYear('summary',2016);await changeYear('availability',2016);
    assert.equal((await availability()).days,366);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('.summary-card .card-heading').screenshot({path:'qa/feature-year-selector-mobile.png'});
    assert.deepEqual(errors,[]);report.independent_selectors_and_lock=true;report.browser_errors=errors;
    fs.writeFileSync('qa/year-selectors-browser-report.json',JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
