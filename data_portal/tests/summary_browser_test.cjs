const path = require('path');
const fs = require('fs');
const assert = require('node:assert/strict');
const {chromium} = require(path.join(process.env.TEMP,'flood_portal_browser/node_modules/playwright'));

(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:1100},deviceScaleFactor:1});
  const errors=[],result={};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error') errors.push(message.text());});
  const readChart=()=>page.evaluate(()=>{
    const graph=document.querySelector('#summary-chart'),viewport=document.querySelector('#summary-chart-viewport');
    return {width:graph._fullLayout.width,client:viewport.clientWidth,scrollWidth:viewport.scrollWidth,left:viewport.scrollLeft,
      ranges:Array.from({length:6},(_,index)=>graph._fullLayout['xaxis'+(index?index+1:'')].range),
      values:JSON.stringify(graph.data.map(trace=>({x:trace.x,y:trace.y}))),
      axes:[...new Set(graph.data.map(trace=>trace.yaxis))],
      domains:Array.from({length:6},(_,index)=>graph._fullLayout['yaxis'+(index?index+1:'')].domain),
      noOtherYears:graph.data.every(trace=>trace.x.every(day=>day.startsWith('2024-'))),
      emptyCounts:graph.data.slice(-3).map(trace=>trace.x.length),
      rainDays:graph.data.find(trace=>trace.type==='bar').x.length,
      withheld:graph.data[1].x.length};
  });
  const fullYear=chart=>{
    for(const range of chart.ranges){assert.equal(range[0].slice(0,10),'2024-01-01');assert.equal(range[1].slice(0,10),'2024-12-31');}
  };
  const waitForLinkedScrollbars=async()=>page.waitForFunction(()=>{
    const viewport=document.querySelector('#summary-chart-viewport');
    const bars=[...document.querySelectorAll('.summary-panel-scrollbar')];
    return bars.length===6&&bars.every(bar=>Math.abs(Number(bar.value)-viewport.scrollLeft)<1);
  });
  const checkDateCursor=async day=>{
    const cursor=await page.evaluate(()=>{
      const marker=document.querySelector('#summary-date-cursor'),graph=document.querySelector('#summary-chart');
      const viewport=document.querySelector('#summary-chart-viewport');
      return {date:marker.dataset.date,hidden:marker.hidden,left:parseFloat(marker.style.left),
        expected:graph._fullLayout.xaxis._offset+graph._fullLayout.xaxis.d2p(marker.dataset.date)-viewport.scrollLeft,
        panels:[...marker.querySelectorAll('.summary-cursor-segment')].map((element,index)=>({top:parseFloat(element.style.top),height:parseFloat(element.style.height),
          expectedTop:graph._fullLayout['yaxis'+(index?index+1:'')]._offset,
          expectedHeight:graph._fullLayout['yaxis'+(index?index+1:'')]._length})),
        line:marker.querySelector('.summary-crosshair-line')?.getBoundingClientRect().height,
        points:[...marker.querySelectorAll('.summary-cursor-segment')].map((segment,index)=>[...segment.querySelectorAll('.summary-reading-point')].map(point=>({
          date:point.dataset.date,value:Number(point.dataset.value),sources:point.dataset.sources,top:parseFloat(point.style.top),
          expectedTop:graph._fullLayout['yaxis'+(index?index+1:'')].d2p(Number(point.dataset.value))
        })))};
    });
    assert.equal(cursor.date,day);assert.equal(cursor.hidden,false);assert.equal(cursor.panels.length,6);
    assert.ok(Math.abs(cursor.left-cursor.expected)<1);
    for(const panel of cursor.panels){assert.ok(Math.abs(panel.top-panel.expectedTop)<1);assert.ok(Math.abs(panel.height-panel.expectedHeight)<1);}
    assert.ok(cursor.line>1000);
    for(const points of cursor.points)for(const point of points){assert.equal(point.date,day);assert.ok(Math.abs(point.top-point.expectedTop)<1);}
    assert.deepEqual(cursor.points.slice(3),[[],[],[]]);
    return cursor;
  };
  const fit=async()=>{
    await page.click('#summary-fit-year');
    await page.waitForFunction(()=>{const g=document.querySelector('#summary-chart'),v=document.querySelector('#summary-chart-viewport');return Math.abs(g._fullLayout.width-v.clientWidth)<2&&v.scrollWidth<=v.clientWidth+1;});
  };
  const wide=async()=>{
    await page.click('#summary-enable-scroll');
    await page.waitForFunction(()=>{const g=document.querySelector('#summary-chart'),v=document.querySelector('#summary-chart-viewport');return g._fullLayout.width>v.clientWidth+500;});
  };
  const readingPosition=async(curve,day)=>page.evaluate(({curve,day})=>{
    const graph=document.querySelector('#summary-chart'),trace=graph.data[curve],bounds=graph.getBoundingClientRect();
    const index=trace.x.indexOf(day),x=graph._fullLayout[trace.xaxis.replace('x','xaxis')],y=graph._fullLayout[trace.yaxis.replace('y','yaxis')];
    return{x:bounds.left+x._offset+x.d2p(day),y:bounds.top+y._offset+y.d2p(trace.y[index])};
  },{curve,day});
  const hoverReading=async(curve,day)=>{
    await page.evaluate(async({curve,day})=>{
      const graph=document.querySelector('#summary-chart'),viewport=document.querySelector('#summary-chart-viewport');
      const trace=graph.data[curve],x=graph._fullLayout[trace.xaxis.replace('x','xaxis')],y=graph._fullLayout[trace.yaxis.replace('y','yaxis')];
      const pixel=x._offset+x.d2p(day);
      viewport.scrollLeft=pixel-graph._fullLayout.margin.l-(viewport.clientWidth-graph._fullLayout.margin.l)/2;
      window.scrollTo({top:scrollY+graph.getBoundingClientRect().top+y._offset-160,behavior:'instant'});
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    },{curve,day});
    const point=await readingPosition(curve,day);
    await page.mouse.move(2,2);await page.mouse.move(point.x,point.y);
    await page.waitForFunction(day=>{const box=document.querySelector('#summary-tooltip');return !box.hidden&&box.dataset.date===day;},day,{timeout:5000});
    return page.locator('#summary-tooltip').innerText();
  };
  try{
    await page.goto('http://127.0.0.1:8787/',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('#discharge-chart').data?.length>=2);
    await page.selectOption('#year','2025');
    await page.waitForFunction(()=>document.querySelector('#discharge-chart').data[0].x.length===0);
    const overviewBefore=await page.evaluate(()=>JSON.stringify(document.querySelector('#discharge-chart').data.map(trace=>({name:trace.name,x:trace.x,y:trace.y}))));
    await page.click('[data-view="summary"]');
    await page.waitForFunction(()=>document.querySelector('#summary-chart').data?.length===10);
    await page.evaluate(()=>document.querySelector('#summary-view').hidden=true);
    await page.click('[data-view="summary"]');
    await page.waitForFunction(()=>!document.querySelector('#summary-view').hidden);
    assert.equal(await page.locator('#summary-window').count(),0);
    const initial=await readChart();fullYear(initial);
    assert.ok(initial.width>initial.client+500);
    assert.equal(initial.rainDays,366);assert.equal(initial.withheld,6);
    assert.equal(initial.axes.length,6);assert.ok(initial.noOtherYears);
    assert.ok(await page.locator('#summary-chart .scatterlayer .points .point').count()>350);
    assert.deepEqual(initial.emptyCounts,[0,0,0]);
    for(let i=1;i<6;i++)assert.ok(initial.domains[i][1]<initial.domains[i-1][0]);
    assert.equal(await page.locator('#summary-axis-gutter').isVisible(),true);
    assert.equal(await page.locator('#summary-row-captions .summary-row-caption').count(),6);
    assert.match(await page.locator('#summary-axis-gutter').innerText(),/Inflow/);
    result.all_366_days_and_independent_axes={chartWidth:initial.width,viewport:initial.client,rainDays:initial.rainDays};

    assert.equal(await page.locator('.summary-panel-scrollbar').count(),6);
    const barGeometry=await page.evaluate(()=>{
      const graph=document.querySelector('#summary-chart');
      return [...document.querySelectorAll('.summary-panel-scrollbar')].map((bar,index)=>({
        top:parseFloat(bar.style.top),plotBottom:graph._fullLayout['yaxis'+(index?index+1:'')]._offset+graph._fullLayout['yaxis'+(index?index+1:'')]._length,
        max:Number(bar.max),sharedMax:document.querySelector('#summary-chart-viewport').scrollWidth-document.querySelector('#summary-chart-viewport').clientWidth
      }));
    });
    for(const bar of barGeometry){assert.ok(bar.top>bar.plotBottom);assert.ok(Math.abs(bar.max-bar.sharedMax)<1);}
    // Every individual graph must be able to move the same full-year canvas.
    for(let index=0;index<6;index++){
      const requested=await page.locator('.summary-panel-scrollbar').nth(index).evaluate((bar,index)=>{
        const target=Math.round(Number(bar.max)*(index+1)/8);bar.value=target;bar.dispatchEvent(new Event('input',{bubbles:true}));return target;
      },index);
      await page.waitForFunction(left=>Math.abs(document.querySelector('#summary-chart-viewport').scrollLeft-left)<1,requested);
      await waitForLinkedScrollbars();fullYear(await readChart());
    }
    const localBar=page.locator('.summary-panel-scrollbar').nth(2);
    await localBar.evaluate(bar=>{bar.value=0;bar.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>document.querySelector('#summary-chart-viewport').scrollLeft===0);
    await waitForLinkedScrollbars();
    await localBar.evaluate(async bar=>{bar.scrollIntoView({block:'center',behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
    const localBox=await localBar.boundingBox();
    const thumb=await localBar.evaluate(bar=>parseFloat(getComputedStyle(bar).getPropertyValue('--thumb-width')));
    await page.mouse.move(localBox.x+thumb/2,localBox.y+localBox.height/2);await page.mouse.down();
    await page.mouse.move(localBox.x+thumb/2+(localBox.width-thumb)*.6,localBox.y+localBox.height/2,{steps:12});await page.mouse.up();
    await page.waitForFunction(()=>{const v=document.querySelector('#summary-chart-viewport');return v.scrollLeft>(v.scrollWidth-v.clientWidth)*.4;});
    await waitForLinkedScrollbars();fullYear(await readChart());
    assert.equal((await readChart()).values,initial.values);
    result.six_per_graph_scrollbars_native_drag_and_sync=true;
    await page.locator('#summary-scroll').evaluate(element=>{element.value='0';element.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>document.querySelector('#summary-chart-viewport').scrollLeft===0);

    await page.locator('#summary-scroll').focus();await page.keyboard.press('ArrowRight');
    await page.waitForFunction(()=>document.querySelector('#summary-chart-viewport').scrollLeft>0);
    await page.locator('#summary-scroll').evaluate(async element=>{element.scrollIntoView({block:'center',behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
    const slider=await page.locator('#summary-scroll').boundingBox();
    await page.mouse.move(slider.x+5,slider.y+slider.height/2);await page.mouse.down();
    await page.mouse.move(slider.x+slider.width*.7,slider.y+slider.height/2,{steps:12});await page.mouse.up();
    await page.waitForFunction(()=>{const v=document.querySelector('#summary-chart-viewport');return v.scrollLeft>(v.scrollWidth-v.clientWidth)*.6;});
    let moved=await readChart();fullYear(moved);assert.equal(moved.values,initial.values);
    await page.locator('#summary-scroll').focus();await page.keyboard.press('End');
    await page.waitForFunction(()=>{const v=document.querySelector('#summary-chart-viewport');return v.scrollLeft>=v.scrollWidth-v.clientWidth-1;});
    assert.match(await page.locator('#summary-visible-dates').innerText(),/31 Dec 2024/);
    assert.equal(await page.locator('#summary-next').isDisabled(),true);
    await page.click('#summary-prev');
    await page.waitForFunction(()=>!document.querySelector('#summary-next').disabled);
    result.native_slider_moves_canvas_without_changing_year=true;

    await fit();const fitted=await readChart();fullYear(fitted);
    assert.equal(fitted.values,initial.values);
    assert.equal(await page.locator('#summary-navigator').isVisible(),false);
    assert.equal(await page.locator('#summary-axis-gutter').isVisible(),false);
    assert.equal(await page.locator('#summary-panel-scrollbars').isVisible(),false);
    await page.screenshot({path:'qa/summary-2024-fit-desktop.png',fullPage:true});
    await wide();const restored=await readChart();fullYear(restored);assert.equal(restored.values,initial.values);
    result.two_full_year_modes=true;

    const normal=await hoverReading(0,'2024-09-22');
    assert.match(normal,/22 September 2024/);assert.match(normal,/WAPDA:\s+22,900 cusecs/);
    assert.match(normal,/FFD:\s+22,900 cusecs/);assert.match(normal,/Both sources report the same flow/);
    assert.doesNotMatch(normal,/19 September|52,000|cross_source/);
    const selectedPoints=await checkDateCursor('2024-09-22');
    assert.deepEqual(selectedPoints.points[0].map(point=>point.value),[22900]);
    assert.equal(selectedPoints.points[0][0].sources,'WAPDA / FFD');
    assert.deepEqual(selectedPoints.points[1].map(point=>point.value),[4000]);
    assert.equal(selectedPoints.points[2].length,1);
    const lockPoint=await readingPosition(0,'2024-09-22');
    await page.mouse.dblclick(lockPoint.x,lockPoint.y);
    assert.equal(await page.getAttribute('#summary-date-cursor','data-locked'),'true');
    assert.equal(await page.locator('#summary-lock-date').innerText(),'Unlock date line');
    assert.match(await page.locator('#summary-selected-date').innerText(),/Locked date: 22 September 2024/);
    const otherDay=await readingPosition(1,'2024-09-19');
    await page.mouse.move(otherDay.x,otherDay.y);
    await page.mouse.click(otherDay.x,otherDay.y);
    await checkDateCursor('2024-09-22');
    assert.match(await page.locator('#summary-tooltip').innerText(),/22 September 2024/);
    assert.doesNotMatch(await page.locator('#summary-tooltip').innerText(),/19 September/);
    await page.locator('.summary-panel-scrollbar').nth(1).evaluate(bar=>{bar.value=Math.min(Number(bar.max),Number(bar.value)+40);bar.dispatchEvent(new Event('input',{bubbles:true}));});
    await waitForLinkedScrollbars();await checkDateCursor('2024-09-22');
    await fit();await checkDateCursor('2024-09-22');
    assert.equal(await page.getAttribute('#summary-date-cursor','data-locked'),'true');
    await wide();await hoverReading(0,'2024-09-22');
    await page.click('#summary-lock-date');
    assert.equal(await page.getAttribute('#summary-date-cursor','data-locked'),'false');
    await hoverReading(1,'2024-09-19');await checkDateCursor('2024-09-19');
    await hoverReading(0,'2024-09-22');
    await page.click('#summary-lock-date');
    assert.equal(await page.getAttribute('#summary-lock-date','aria-pressed'),'true');
    await page.keyboard.press('Escape');
    assert.equal(await page.getAttribute('#summary-lock-date','aria-pressed'),'false');
    await hoverReading(0,'2024-09-22');
    result.double_click_lock_unlock_escape_and_scroll_persistence=true;
    await page.screenshot({path:'qa/summary-tooltip-normal.png'});
    // The crosshair also works over an empty variable panel, without inventing
    // a zero or copying a reading from a different date into that panel.
    const emptyPosition=await page.evaluate(async()=>{
      const graph=document.querySelector('#summary-chart'),axis=graph._fullLayout.yaxis4;
      window.scrollTo({top:scrollY+graph.getBoundingClientRect().top+axis._offset-160,behavior:'instant'});
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      const bounds=graph.getBoundingClientRect();
      return {x:bounds.left+graph._fullLayout.xaxis._offset+graph._fullLayout.xaxis.d2p('2024-09-22'),y:bounds.top+axis._offset+axis._length/2};
    });
    await page.mouse.move(emptyPosition.x,emptyPosition.y);
    await page.waitForFunction(()=>!document.querySelector('#summary-tooltip').hidden&&document.querySelector('#summary-tooltip').dataset.variable==='y4');
    assert.match(await page.locator('#summary-tooltip').innerText(),/No saved reading for this variable on this date/);
    await checkDateCursor('2024-09-22');
    const uncertain=await hoverReading(1,'2024-09-19');
    assert.match(uncertain,/24,600 cusecs/);assert.match(uncertain,/Needs checking \u2014 excluded from training/);
    assert.match(uncertain,/52,000 cusecs/);assert.match(uncertain,/website lists 2 September/);
    assert.doesNotMatch(uncertain,/22 September|cross_source/);
    const uncertainPoints=await checkDateCursor('2024-09-19');
    assert.deepEqual(uncertainPoints.points[0].map(point=>point.value).sort((a,b)=>a-b),[24600,52000]);
    await page.screenshot({path:'qa/summary-tooltip-uncertain.png'});
    const outflow=await hoverReading(4,'2024-09-22');assert.match(outflow,/Water leaving Marala/);assert.match(outflow,/4,000 cusecs/);
    await page.mouse.move(2,2);
    await checkDateCursor('2024-09-22');
    // Moving the canvas changes the guide's screen position, not its date.
    const guideBefore=await checkDateCursor('2024-09-22');
    await page.evaluate(()=>document.querySelector('#summary-chart-viewport').scrollLeft+=80);
    await page.waitForFunction(left=>Math.abs(parseFloat(document.querySelector('#summary-date-cursor').style.left)-(left-80))<1,guideBefore.left);
    await checkDateCursor('2024-09-22');
    await fit();await checkDateCursor('2024-09-22');
    await wide();
    await hoverReading(0,'2024-09-22');
    result.shared_date_line_in_all_six_panels=true;
    result.continuous_crosshair_with_actual_reading_points=true;
    result.plain_language_single_date_hover={normal,uncertain};

    await page.evaluate(()=>{const v=document.querySelector('#summary-chart-viewport');v.scrollLeft=100;});
    const viewport=await page.locator('#summary-chart-viewport').boundingBox();
    await page.mouse.move(viewport.x+200,220);await page.mouse.wheel(250,0);
    await page.waitForFunction(()=>document.querySelector('#summary-chart-viewport').scrollLeft>150);
    fullYear(await readChart());result.native_horizontal_wheel=true;
    await page.screenshot({path:'qa/summary-2024-wide-desktop.png',fullPage:true});
    await page.click('[data-view="overview"]');
    await page.waitForFunction(()=>!document.querySelector('#filters').hidden);
    assert.equal(await page.inputValue('#year'),'2025');
    const overviewAfter=await page.evaluate(()=>JSON.stringify(document.querySelector('#discharge-chart').data.map(trace=>({name:trace.name,x:trace.x,y:trace.y}))));
    assert.equal(overviewBefore,overviewAfter);result.existing_graphs_preserved=true;

    await page.setViewportSize({width:390,height:844});
    await page.goto('http://127.0.0.1:8787/?check=full-year#summary',{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('#summary-chart').data?.length===10);
    await wide();fullYear(await readChart());
    await page.locator('.summary-panel-scrollbar').nth(4).evaluate(bar=>{bar.value=bar.max;bar.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>{const v=document.querySelector('#summary-chart-viewport');return v.scrollLeft>=v.scrollWidth-v.clientWidth-1;});
    await waitForLinkedScrollbars();
    await hoverReading(0,'2024-09-22');const tooltip=await page.locator('#summary-tooltip').boundingBox();
    assert.ok(tooltip.x>=0&&tooltip.x+tooltip.width<=390);
    await checkDateCursor('2024-09-22');
    await page.mouse.move(2,2);
    const mobile=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));
    assert.ok(mobile.scroll<=mobile.width+1,JSON.stringify(mobile));
    await page.screenshot({path:'qa/summary-2024-wide-mobile.png',fullPage:true});
    await fit();fullYear(await readChart());
    await checkDateCursor('2024-09-22');
    await page.click('#summary-lock-date');
    assert.equal(await page.getAttribute('#summary-date-cursor','data-locked'),'true');
    await page.screenshot({path:'qa/summary-2024-fit-mobile.png',fullPage:true});
    await page.click('#summary-clear-date');
    assert.equal(await page.locator('#summary-date-cursor').isVisible(),false);
    assert.equal(await page.locator('#summary-lock-date').isVisible(),false);
    assert.equal(await page.getAttribute('#summary-date-cursor','data-locked'),'false');
    assert.match(await page.locator('#summary-selected-date').innerText(),/Move across a graph or tap/);
    result.mobile_modes_and_hover=mobile;assert.deepEqual(errors,[]);result.browser_errors=errors;
    fs.writeFileSync('qa/summary-browser-report.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
