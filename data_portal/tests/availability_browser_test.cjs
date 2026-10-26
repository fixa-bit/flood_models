const path=require('path');
const fs=require('fs');
const assert=require('node:assert/strict');
const {chromium}=require(path.join(process.env.TEMP,'flood_portal_browser/node_modules/playwright'));

(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:1100},deviceScaleFactor:1});
  const errors=[],result={};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  const hoverCell=async(index,day)=>{
    await page.evaluate(async({index,day})=>{
      const graph=document.querySelector('#availability-chart'),viewport=document.querySelector('#availability-viewport');
      const x=graph._fullLayout.xaxis,y=graph._fullLayout.yaxis;
      viewport.scrollLeft=x._offset+x.d2p(day)-graph._fullLayout.margin.l-(viewport.clientWidth-graph._fullLayout.margin.l)/2;
      window.scrollTo({top:scrollY+graph.getBoundingClientRect().top-120,behavior:'instant'});
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    },{index,day});
    const point=await page.evaluate(({index,day})=>{
      const graph=document.querySelector('#availability-chart'),bounds=graph.getBoundingClientRect();
      return {x:bounds.left+graph._fullLayout.xaxis._offset+graph._fullLayout.xaxis.d2p(day),
        y:bounds.top+graph._fullLayout.yaxis._offset+graph._fullLayout.yaxis.d2p(graph.data[0].y[index])};
    },{index,day});
    await page.mouse.move(2,2);await page.mouse.move(point.x,point.y);
    await page.waitForFunction(()=>document.querySelector('#availability-chart .hoverlayer')?.textContent.length>10);
    return page.locator('#availability-chart .hoverlayer').textContent();
  };
  try{
    await page.goto('http://127.0.0.1:8787/?check=availability#summary',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('#availability-chart').data?.length===2);
    const inventory=await page.evaluate(()=>{
      const graph=document.querySelector('#availability-chart'),heat=graph.data[0],dates=heat.x;
      const day=value=>dates.indexOf(value);
      return {rows:heat.y,days:dates.length,span:[dates[0],dates.at(-1)],
        present:heat.z.map(row=>row.filter(value=>value>0).length),
        reviews:heat.y.map(label=>graph.data[1].y.filter(value=>value===label).length),
        dateLevelRows:heat.z.map(row=>row.length),
        zeroRainDayPresent:heat.z[2][day('2024-09-22')]>0,
        withheldInflow:heat.z[0][day('2024-09-19')]>0,
        lateDischargeMissing:heat.z[0][day('2024-12-20')]===0,
        fullYearRain:heat.z[2][day('2024-12-31')]>0,
        february29:dates.includes('2024-02-29'),
        unknownTime:heat.customdata[0][day('2024-01-01')][4],
        confirmedTime:heat.customdata[0][day('2024-12-19')][4],
        precipitationPeriod:heat.customdata[2][day('2016-03-01')][4],
        earliestPeak:heat.z[5][0]>0,earlyDailyMissing:heat.z[0][0]===0&&heat.z[2][0]===0,
        irsaLatest:heat.z[3][day('2026-10-23')]>0&&heat.z[4][day('2026-10-23')]>0,
        missingLatestRain:heat.z[2][day('2026-10-22')]===0,
        measurementValuesAbsent:heat.customdata.every(row=>row.every(detail=>!/22,900|24,600|52,000|cusecs/.test(detail.join(' ')))),
        width:graph._fullLayout.width,
        numericScaleShown:heat.showscale,colors:[...document.querySelectorAll('#availability-legend i')].map(element=>getComputedStyle(element).backgroundColor)};
    });
    assert.equal(inventory.days,20568);assert.equal(inventory.rows.length,6);
    assert.deepEqual(inventory.span,['1970-07-02','2026-10-23']);
    assert.deepEqual(inventory.present,[3455,359,3887,8,8,30]);
    assert.deepEqual(inventory.reviews,[18,13,3887,0,0,0]);
    assert.ok(inventory.zeroRainDayPresent&&inventory.withheldInflow&&inventory.lateDischargeMissing&&inventory.fullYearRain&&inventory.february29);
    assert.deepEqual(inventory.dateLevelRows,[20568,20568,20568,20568,20568,20568]);
    assert.ok(inventory.earliestPeak&&inventory.earlyDailyMissing&&inventory.irsaLatest&&inventory.missingLatestRain);
    assert.ok(inventory.width<=16000);
    assert.match(inventory.unknownTime,/not confirmed/);assert.match(inventory.confirmedTime,/06:00/);
    assert.match(inventory.precipitationPeriod,/05:00/);
    assert.ok(inventory.measurementValuesAbsent);
    assert.equal(inventory.numericScaleShown,false);assert.equal(new Set(inventory.colors).size,6);
    result.calendar=inventory.present;result.review_days=inventory.reviews;
    result.zeroes_withheld_dates_and_time_certainty=true;
    result.full_collected_history={start:inventory.span[0],end:inventory.span[1],days:inventory.days};
    const years=await page.locator('#availability-year option').evaluateAll(options=>options.map(option=>option.value));
    assert.ok(years.includes('1970')&&years.includes('2016')&&years.includes('2026'));
    await page.selectOption('#availability-year','2016');
    await page.waitForFunction(()=>!document.querySelector('#availability-year').disabled&&document.querySelector('#availability-chart').data[0].x[0]==='2016-01-01');
    assert.ok(await page.evaluate(()=>{
      const heat=document.querySelector('#availability-chart').data[0];
      return heat.x.length===366&&heat.x.at(-1)==='2016-12-31'&&heat.x.includes('2016-02-29');
    }));
    assert.equal(await page.inputValue('#summary-year'),'2024');
    await page.selectOption('#availability-year','all');
    await page.waitForFunction(()=>!document.querySelector('#availability-year').disabled&&document.querySelector('#availability-chart').data[0].x.length===20568);

    // Main-graph scrolling must not change this chart, in either direction.
    await page.locator('.summary-panel-scrollbar').first().evaluate(bar=>{bar.value=500;bar.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>document.querySelector('#summary-chart-viewport').scrollLeft===500);
    assert.equal(await page.locator('#availability-viewport').evaluate(element=>element.scrollLeft),0);
    const normal=await hoverCell(0,'2024-09-22');
    assert.match(normal,/Reading saved/);assert.match(normal,/WAPDA.*FFD/);
    assert.match(normal,/observation hour not confirmed/);assert.match(normal,/06:00 Pakistan/);
    assert.doesNotMatch(normal,/22,900|cusecs/);
    assert.equal(await page.locator('#summary-chart-viewport').evaluate(element=>element.scrollLeft),500);
    const missing=await hoverCell(3,'2024-09-22');assert.match(missing,/No saved reading/);
    const period=await hoverCell(2,'2024-09-22');assert.match(period,/24-hour period/);assert.match(period,/on hold/);
    await page.mouse.move(2,2);

    await page.locator('#availability-scroll').evaluate(element=>{element.value=0;element.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.locator('#availability-scroll').evaluate(async element=>{element.scrollIntoView({block:'center',behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
    const slider=await page.locator('#availability-scroll').boundingBox();
    await page.mouse.move(slider.x+7,slider.y+slider.height/2);await page.mouse.down();
    await page.mouse.move(slider.x+slider.width*.7,slider.y+slider.height/2,{steps:12});await page.mouse.up();
    await page.waitForFunction(()=>{const viewport=document.querySelector('#availability-viewport');return viewport.scrollLeft>(viewport.scrollWidth-viewport.clientWidth)*.6;});
    assert.equal(await page.locator('#summary-chart-viewport').evaluate(element=>element.scrollLeft),500);
    const ownPosition=await page.locator('#availability-viewport').evaluate(element=>element.scrollLeft);
    await page.click('#summary-fit-year');
    await page.waitForFunction(()=>document.querySelector('#summary-navigator').hidden);
    assert.equal(await page.locator('#availability-viewport').evaluate(element=>element.scrollLeft),ownPosition);
    result.independent_native_scroll_and_modes=true;
    await page.selectOption('#availability-year','2024');
    await page.waitForFunction(()=>!document.querySelector('#availability-year').disabled&&document.querySelector('#availability-chart').data[0].x[0]==='2024-01-01');
    assert.deepEqual(await page.evaluate(()=>document.querySelector('#availability-chart').data[0].z.map(row=>row.filter(Boolean).length)),[354,120,366,0,0,0]);
    await page.locator('.availability-card').screenshot({path:'qa/availability-selected-year-desktop.png'});

    await page.setViewportSize({width:390,height:844});
    await page.goto('http://127.0.0.1:8787/?check=availability-mobile#summary',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('#availability-chart').data?.length===2);
    await page.locator('#availability-scroll').evaluate(element=>{element.value=element.max;element.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>{const viewport=document.querySelector('#availability-viewport');return viewport.scrollLeft>=viewport.scrollWidth-viewport.clientWidth-1;});
    assert.equal(await page.locator('#summary-chart-viewport').evaluate(element=>element.scrollLeft),0);
    assert.match(await page.locator('#availability-visible-dates').innerText(),/23 October 2026/);
    const mobile=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));
    assert.ok(mobile.scroll<=mobile.width+1,JSON.stringify(mobile));
    await page.locator('.availability-card').screenshot({path:'qa/availability-all-years-mobile.png'});
    result.mobile_layout=mobile;assert.deepEqual(errors,[]);result.browser_errors=errors;
    fs.writeFileSync('qa/availability-browser-report.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
