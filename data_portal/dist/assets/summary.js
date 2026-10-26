'use strict';

// Feature plots share their own year selector. The availability calendar and
// other portal views keep independent filters; source readings are unchanged.
window.FloodSummary = (() => {
  const DAY = 86400000;
  let START = Date.UTC(2024, 0, 1);
  let DAYS = 366;
  let END = START + DAYS * DAY;
  const PANEL_GAP=.065;
  const palette = {inflow:'#75d0ac', ffd:'#8db9df', rain:'#efb35e', conflict:'#ed9f83', muted:'#9eafa2'};
  const current = {year:2024,mode:'scroll', bound:false,locked:false};
  const select = id => document.getElementById(id);
  const inYear = rows => rows.filter(row => row.date.startsWith(current.year+'-'));
  const iso = milliseconds => new Date(milliseconds).toISOString().slice(0, 10);
  const displayDate = milliseconds => new Date(milliseconds).toLocaleDateString('en-GB', {timeZone:'UTC', day:'2-digit', month:'short', year:'numeric'});
  const axisName = (prefix, index) => prefix + (index === 0 ? '' : index + 1);
  const escape = value => String(value).replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const longDate = (day,year=true) => new Date(day+'T00:00:00Z').toLocaleDateString('en-GB',{
    timeZone:'UTC',day:'numeric',month:'long',...(year?{year:'numeric'}:{})});
  const amount = value => Number(value).toLocaleString('en-US',{maximumFractionDigits:3});

  function configureYear(data) {
    current.data=data;
    const years=['inflow','ffd','precipitation','irsa','peaks'].flatMap(key=>data[key].map(row=>Number(row.date.slice(0,4))));
    const first=Math.min(...years),last=Math.max(...years);
    if(current.year<first||current.year>last) current.year=last;
    const field=select('summary-year');
    field.replaceChildren(...Array.from({length:last-first+1},(_,index)=>new Option(String(first+index),String(first+index))));
    field.value=String(current.year);
    START=Date.UTC(current.year,0,1);END=Date.UTC(current.year+1,0,1);DAYS=Math.round((END-START)/DAY);
    select('summary-eyebrow').textContent='MARALA · FEATURE HISTORY';
    select('summary-year-badge').textContent=String(current.year);
    select('summary-chart-title').textContent=`Marala · January–December ${current.year}`;
    select('summary-fit-year').textContent=`Full ${current.year} — one screen`;
    select('summary-enable-scroll').textContent=`Full ${current.year} — scrollable`;
    select('summary-date-label').textContent=`Full year: ${displayDate(START)} — ${displayDate(END-DAY)}`;
    select('summary-first-date').textContent=displayDate(START);
    select('summary-last-date').textContent=displayDate(END-DAY);
    select('summary-scroll').setAttribute('aria-label',`Scroll horizontally across the full ${current.year} chart`);
    select('summary-chart-viewport').setAttribute('aria-label',`Full ${current.year} chart. Scroll horizontally to browse January through December.`);
    select('summary-chart').setAttribute('aria-label',`Six stacked Marala variable plots for ${current.year}, with separate y-axes and a shared date axis`);
    document.querySelector('.summary-modes').setAttribute('aria-label',`Full ${current.year} display mode`);
  }

  function groupByDate(rows) {
    const groups=new Map();
    for(const row of rows) {
      if(!groups.has(row.date)) groups.set(row.date,[]);
      groups.get(row.date).push(row);
    }
    return groups;
  }

  function hideTooltip() { select('summary-tooltip').hidden=true; }

  function selectedReadings(day,index) {
    const data=current.hoverData,readings=[];
    const add=(source,value,color,flagged=false,unit='cusecs')=>{
      if(value!==null&&value!==undefined&&Number.isFinite(Number(value)))
        readings.push({source,value:Number(value),color,flagged,unit});
    };
    if(index===0) {
      for(const row of data.wapda.get(day)||[]) add('WAPDA',row.source_value,row.eligible?palette.inflow:palette.rain,!row.eligible);
      for(const row of data.ffd.get(day)||[]) add('FFD',row.inflow,row.flag?palette.conflict:palette.ffd,row.flag);
    } else if(index===1) {
      for(const row of data.ffd.get(day)||[]) add('FFD',row.outflow,row.flag?palette.conflict:palette.ffd,row.flag);
    } else if(index===2) {
      for(const row of data.rain.get(day)||[]) add('NASA POWER',row.value,palette.rain,true,'mm/day');
    } else if(index===3||index===4) {
      for(const row of data.irsa.get(day)||[]) add('IRSA',row[index===3?'inflow':'outflow'],index===3?palette.inflow:palette.ffd);
    } else {
      for(const row of data.peaks.get(day)||[]) add('PMD',row.value,'#c6abd8');
    }
    // Matching source readings share one point at their actual y-value.
    const grouped=new Map();
    for(const reading of readings) {
      const key=reading.value+'|'+reading.unit;
      if(!grouped.has(key)) grouped.set(key,{...reading,sources:[]});
      const group=grouped.get(key);
      if(!group.sources.includes(reading.source)) group.sources.push(reading.source);
      if(reading.flagged) {group.flagged=true;group.color=reading.color;}
    }
    return [...grouped.values()];
  }

  function updateDateCursor() {
    const marker=select('summary-date-cursor'),graph=select('summary-chart');
    const viewport=select('summary-chart-viewport');
    const day=current.selectedDate;
    const locked=Boolean(day&&current.locked);
    select('summary-clear-date').hidden=!day;
    const lockButton=select('summary-lock-date');
    lockButton.hidden=!day;
    lockButton.textContent=locked?'Unlock date line':'Lock date line';
    lockButton.setAttribute('aria-pressed',String(locked));
    marker.dataset.locked=String(locked);
    select('summary-selected-date').textContent=day
      ? (locked?`Locked date: ${longDate(day)} — readings stay fixed. Unlock the date line or press Esc to move it again.`
        : `Selected date: ${longDate(day)} — aligned across all variables. Double-click a plot to lock this date.`)
      : 'Move across a graph or tap a date to see its crosshair and reading points on every variable. Double-click to lock it.';
    if(!day||!graph._fullLayout?._size) {marker.hidden=true;return;}
    const layout=graph._fullLayout;
    const left=layout.xaxis._offset+layout.xaxis.d2p(day)-viewport.scrollLeft;
    marker.dataset.date=day;
    // Keep the selection when scrolling, but never draw it over the pinned
    // y-axis labels or outside the currently visible part of the full-year plot.
    marker.hidden=left<layout.margin.l||left>viewport.clientWidth;
    marker.style.left=left+'px';
    if(marker.querySelectorAll('.summary-cursor-segment').length!==current.rows.length) {
      const line=document.createElement('div');
      line.className='summary-crosshair-line';
      marker.replaceChildren(line,...current.rows.map(()=>{
        const segment=document.createElement('div');
        segment.className='summary-cursor-segment';
        return segment;
      }));
    }
    const line=marker.querySelector('.summary-crosshair-line');
    const first=layout.yaxis,last=layout[axisName('yaxis',current.rows.length-1)];
    line.style.top=first._offset+'px';
    line.style.height=(last._offset+last._length-first._offset)+'px';
    [...marker.querySelectorAll('.summary-cursor-segment')].forEach((segment,index)=>{
      const axis=layout[axisName('yaxis',index)];
      segment.style.top=axis._offset+'px';
      segment.style.height=axis._length+'px';
      segment.replaceChildren();
      const labels=[];
      const spaceRight=viewport.clientWidth-left-14,spaceLeft=left-layout.margin.l-14;
      const onRight=spaceRight>=Math.min(220,spaceLeft);
      const labelWidth=Math.max(80,Math.min(220,onRight?spaceRight:spaceLeft));
      for(const reading of selectedReadings(day,index)) {
        const rawY=axis.d2p(reading.value);
        if(!Number.isFinite(rawY)||rawY<-.5||rawY>axis._length+.5) continue;
        const y=Math.max(0,Math.min(axis._length,rawY));
        const point=document.createElement('span');
        point.className='summary-reading-point';
        point.dataset.date=day;point.dataset.value=reading.value;
        point.dataset.sources=reading.sources.join(' / ');
        point.dataset.flagged=String(reading.flagged);
        point.style.top=y+'px';point.style.setProperty('--reading-color',reading.color);
        segment.append(point);
        const label=document.createElement('span');
        label.className='summary-reading-label';
        label.textContent=`${reading.sources.join(' / ')}: ${amount(reading.value)} ${reading.unit}${reading.flagged?' (needs checking)':''}`;
        label.style.maxWidth=labelWidth+'px';label.style.setProperty('--reading-color',reading.color);
        if(onRight) label.style.left='10px';else label.style.right='10px';
        segment.append(label);
        labels.push({label,y,height:label.offsetHeight});
      }
      // Separate labels for disagreeing readings while leaving each point at
      // its true measured y-position on the crosshair.
      labels.sort((a,b)=>a.y-b.y);
      let bottom=0;
      for(const item of labels) {
        item.top=Math.max(bottom,Math.min(axis._length-item.height,item.y-item.height/2));
        bottom=item.top+item.height+3;
      }
      let next=axis._length;
      for(const item of [...labels].reverse()) {
        item.top=Math.max(0,Math.min(item.top,next-item.height));
        item.label.style.top=item.top+'px';
        next=item.top-3;
      }
    });
  }

  function moveCrosshair(event) {
    const graph=select('summary-chart'),viewport=select('summary-chart-viewport');
    if(!graph._fullLayout?._size||current.rendering) return;
    const layout=graph._fullLayout,bounds=graph.getBoundingClientRect(),view=viewport.getBoundingClientRect();
    if(event.clientX<view.left+layout.margin.l||event.clientX>view.right) return;
    const x=event.clientX-bounds.left-layout.xaxis._offset,y=event.clientY-bounds.top;
    if(x<0||x>layout.xaxis._length||!current.rows.some((_,index)=>{
      const axis=layout[axisName('yaxis',index)];return y>=axis._offset&&y<=axis._offset+axis._length;
    })) return;
    const index=Math.max(0,Math.min(DAYS-1,Math.round(x/layout.xaxis._length*DAYS)));
    const day=current.locked&&current.selectedDate?current.selectedDate:iso(START+index*DAY);
    const panel=current.rows.findIndex((_,index)=>{
      const axis=layout[axisName('yaxis',index)];return y>=axis._offset&&y<=axis._offset+axis._length;
    });
    showDateTooltip(day,axisName('y',panel),event);
    return true;
  }

  function unlockDate() {
    current.locked=false;
    hideTooltip();updateDateCursor();
  }

  function lockDate() {
    if(!current.selectedDate||current.locked) return;
    current.locked=true;updateDateCursor();
  }

  function reading(source,value,unit='cusecs') {
    return `<div><dt>${escape(source)}:</dt><dd><strong>${amount(value)}</strong> ${unit}</dd></div>`;
  }

  function tooltipContent(day,axis) {
    const saved=current.hoverData;
    const wapda=saved.wapda.get(day)?.[0];
    const ffd=saved.ffd.get(day)||[];
    const field=axis==='y2'?'outflow':'inflow';
    const normal=ffd.filter(row=>!row.flag),conflicts=ffd.filter(row=>row.flag);
    let title,values='',status='',explanation='',unit='Water flow is measured in cubic feet per second (cusecs).',warning=false;
    if(axis==='y'||axis==='y2') {
      const incoming=axis==='y';
      title=incoming?'Water entering Marala':'Water leaving Marala';
      const withheld=incoming&&wapda&&!wapda.eligible;
      if(incoming&&wapda) values+=reading('WAPDA',wapda.source_value);
      // A withheld point with a date-conflicted bulletin uses the approved short
      // explanation below. Preserve all original records in the dataset.
      if(!(withheld&&conflicts.length)) normal.forEach((row,index)=>{
        values+=reading(normal.length>1?`FFD record ${index+1}`:'FFD',row[field]);
      });
      if(withheld) {
        warning=true;
        status='Needs checking — excluded from training';
        if(!conflicts.length) explanation=wapda.source_value===0
          ? 'The source reports zero flow. This reading needs confirmation.'
          : 'The sources report different flows for this date. The reading needs checking before training.';
      } else if(conflicts.length) {
        warning=true;
        status='Needs checking — FFD record date is unclear';
      } else if(incoming&&wapda&&normal.length&&normal.every(row=>Math.abs(row.inflow-wapda.source_value)<.000001)) {
        status='Check: Both sources report the same flow.';
      } else if(incoming&&wapda&&normal.length) {
        warning=true;
        status='Needs checking — the sources report different flows.';
      } else {
        status=incoming&&wapda?'Check: No FFD reading is saved for this date.':'Recorded by FFD at 06:00 Pakistan time.';
      }
      for(const row of conflicts) {
        explanation+=(explanation?' ':'')+`Another FFD record shows ${amount(row[field])} cusecs, but its date is unclear: the bulletin says ${longDate(day,false)}, while the website lists ${longDate(row.archive_date,false)}.`;
      }
    } else if(axis==='y3') {
      title='Precipitation over the upstream area';
      const rain=saved.rain.get(day)?.[0];
      if(rain&&rain.value!==null) values=reading('NASA POWER',rain.value,'mm/day');
      warning=true;
      status='Needs checking — excluded from training';
      explanation='Different source downloads gave different results. These saved precipitation values need checking before training.';
      unit='One value covers 05:00 to the next 05:00 Pakistan time, averaged over the upstream catchment.';
    } else if(axis==='y4'||axis==='y5') {
      const incoming=axis==='y4',row=saved.irsa.get(day)?.[0];
      title=incoming?'Average water entering Marala':'Average water leaving Marala';
      if(row) values=reading('IRSA',row[incoming?'inflow':'outflow']);
      status='Daily average; the exact start and end hours are not stated.';
    } else {
      title='Highest flow during a selected flood';
      for(const row of saved.peaks.get(day)||[]) values+=reading('PMD journal',row.value);
      status='A selected flood peak, not a daily average.';
    }
    if(!values) return `<h3>${escape(longDate(day))} — ${title}</h3><p class="hover-explanation">No saved reading for this variable on this date.</p>`;
    return `<h3>${escape(longDate(day))} — ${title}</h3><dl>${values}</dl>`+
      `<p class="hover-status${warning?' warning':''}">${escape(status)}</p>`+
      (explanation?`<p class="hover-explanation">${escape(explanation)}</p>`:'')+
      `<p class="hover-unit">${escape(unit)}</p>`;
  }

  function showDateTooltip(day,axis,event) {
    // One shared calendar date supplies every marker and source value. Never
    // combine the nearest point from each source at different dates.
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!day.startsWith(current.year+'-')) return;
    if(current.locked&&current.selectedDate) day=current.selectedDate;
    current.selectedDate=day;
    updateDateCursor();
    const tooltip=select('summary-tooltip');
    tooltip.dataset.date=day;
    tooltip.dataset.variable=axis;
    tooltip.innerHTML=tooltipContent(day,axis);
    tooltip.hidden=false;
    const bounds=select('summary-chart').getBoundingClientRect();
    const x=event?.clientX??bounds.left+120,y=event?.clientY??bounds.top+80;
    const width=tooltip.offsetWidth,height=tooltip.offsetHeight;
    tooltip.style.left=Math.max(12,Math.min(x+18,window.innerWidth-width-12))+'px';
    tooltip.style.top=Math.max(12,Math.min(y+18,window.innerHeight-height-12))+'px';
  }

  function gaps(rows, key) {
    const values = [];
    let previous;
    for (const row of [...rows].sort((a,b) => a.date.localeCompare(b.date))) {
      if (previous && Date.parse(row.date) - Date.parse(previous) > DAY)
        values.push({date:iso(Date.parse(previous) + DAY), [key]:null});
      values.push(row);
      previous = row.date;
    }
    return values;
  }

  function flowTrace(rows, key, name, color, rowIndex, extra={}) {
    const data = gaps(rows, key);
    return {
      type:'scatter', mode:'lines+markers', x:data.map(row => row.date), y:data.map(row => row[key]),
      name, xaxis:axisName('x',rowIndex), yaxis:axisName('y',rowIndex),
      connectgaps:false, line:{color,width:1.7},marker:{color,size:3.5,symbol:'circle-open',line:{color,width:.8}}, ...extra,
    };
  }

  function ffdConflict(rows, key, rowIndex) {
    return {
      type:'scatter', mode:'markers', name:'FFD printed/archive date conflict',
      x:rows.map(row => row.date), y:rows.map(row => row[key]),
      xaxis:axisName('x',rowIndex), yaxis:axisName('y',rowIndex),
      marker:{color:palette.conflict, size:8, symbol:'diamond-open'},
    };
  }

  function tracks(data) {
    const inflow = inYear(data.inflow);
    const ffd = inYear(data.ffd);
    const irsa = inYear(data.irsa);
    const peaks = inYear(data.peaks);
    const rain = inYear(data.precipitation);
    const flagged = inflow.filter(row => !row.eligible);
    const ffdNormal = ffd.filter(row => !row.flag);
    const ffdFlagged = ffd.filter(row => row.flag);
    const rows = [
      {title:'Inflow discharge', detail:'WAPDA + FFD · Marala station', unit:'Inflow (cusecs)', count:inflow.length+ffd.length,empty:`No inflow readings saved for ${current.year}.`},
      {title:'Outflow discharge', detail:'FFD · 06:00 Pakistan snapshot', unit:'Outflow (cusecs)', count:ffd.length,empty:`No outflow readings saved for ${current.year}.`},
      {title:'Catchment precipitation', detail:'24-hour amount · area average · HOLD', unit:'Precip. (mm/day)', count:rain.filter(row=>row.value!==null).length,empty:`No precipitation readings saved for ${current.year}.`},
      {title:'Daily mean inflow', detail:'IRSA · separate measurement basis', unit:'Mean inflow (cusecs)', count:irsa.length, empty:`No ${current.year} records. Saved IRSA means cover 16–23 Oct 2026.`},
      {title:'Daily mean outflow', detail:'IRSA · separate measurement basis', unit:'Mean outflow (cusecs)', count:irsa.length, empty:`No ${current.year} records. Saved IRSA means cover 16–23 Oct 2026.`},
      {title:'Selected event peak discharge', detail:'PMD journal · event maxima', unit:'Peak (cusecs)', count:peaks.length, empty:`No ${current.year} records. Saved selected events cover 1970–2016.`},
    ];
    const traces = [
      flowTrace(inflow,'value','Eligible WAPDA inflow',palette.inflow,0),
      {type:'scatter',mode:'markers',name:'Withheld WAPDA source value',x:flagged.map(row=>row.date),y:flagged.map(row=>row.source_value),
       xaxis:'x',yaxis:'y',marker:{color:palette.rain,size:8,symbol:'circle-open',line:{width:2}}},
      flowTrace(ffdNormal,'inflow','FFD 06:00 inflow',palette.ffd,0,{line:{color:palette.ffd,width:1.2,dash:'dot'}}),
      ffdConflict(ffdFlagged,'inflow',0),
      flowTrace(ffdNormal,'outflow','FFD 06:00 outflow',palette.ffd,1),
      ffdConflict(ffdFlagged,'outflow',1),
      {type:'bar',name:'Saved catchment precipitation · HOLD',x:rain.map(row=>row.date),y:rain.map(row=>row.value),xaxis:'x3',yaxis:'y3',
       marker:{color:palette.rain,opacity:.8}},
      flowTrace(irsa,'inflow','IRSA daily mean inflow',palette.inflow,3),
      flowTrace(irsa,'outflow','IRSA daily mean outflow',palette.ffd,4),
      {type:'scatter',mode:'markers',name:'Selected PMD event maximum',x:peaks.map(row=>row.date),y:peaks.map(row=>row.value),xaxis:'x6',yaxis:'y6',
       marker:{color:'#c6abd8',size:8}},
    ];
    // Keep Plotly hover events, but replace its multi-date box with a plain-
    // language card that looks up sources on the exact selected calendar date.
    traces.forEach(trace=>{trace.hoverinfo='none';});
    return {rows,traces,inflow,ffd,rain};
  }

  function range() {
    return [iso(START),new Date(END-1).toISOString()];
  }

  function ticks() {
    if(current.mode==='scroll')
      return Array.from({length:Math.ceil(DAYS/7)},(_,index)=>iso(START+index*7*DAY));
    return Array.from({length:6},(_,index)=>iso(Date.UTC(current.year,index*2,1)));
  }

  function chartWidth() {
    const available=select('summary-chart-viewport').clientWidth;
    return current.mode==='scroll'?Math.max(DAYS*8+108,available*2):available;
  }

  function annotations(rows) {
    if(current.mode==='scroll') return [];
    const result=[];
    rows.forEach((row,index)=>{
      const top=1-index/rows.length,bottom=top-1/rows.length+PANEL_GAP;
      let heading=`<b>${row.title}</b> <span style="font-size:10px;color:#9eafa2">· ${row.detail}</span>`;
      if(window.innerWidth<700) heading=heading.replace('</b> <span','</b><br><span');
      result.push({xref:'paper',yref:'paper',x:0,y:top+.03,xanchor:'left',yanchor:'bottom',
        text:heading,showarrow:false,font:{size:12,color:'#e1e9dc'},align:'left'});
      if(!row.count) result.push({xref:'paper',yref:'paper',x:.5,y:(top+bottom)/2,
        text:row.empty.replace('. Eight ','.<br>Eight ').replace('. The saved ','.<br>The saved '),
        showarrow:false,font:{size:11,color:palette.muted},align:'center'});
    });
    return result;
  }

  function pinAxes() {
    const graph=select('summary-chart'),gutter=select('summary-axis-gutter'),captions=select('summary-row-captions');
    const scrolling=current.mode==='scroll';
    gutter.hidden=captions.hidden=!scrolling;
    gutter.replaceChildren();captions.replaceChildren();
    positionPanelScrollbars();
    if(!scrolling||!graph._fullLayout) return;
    const layout=graph._fullLayout;
    gutter.style.width=layout.margin.l+'px';
    captions.style.left=layout.margin.l+'px';
    // Copy only the y-axis labels and tick marks, so their scales stay visible
    // while the original full-year canvas scrolls horizontally underneath.
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('width',layout.margin.l);
    svg.setAttribute('height',layout.height);
    for(const node of graph.querySelectorAll('.yaxislayer-above, g[class^="g-y"]')) {
      if(node.classList.contains('yaxislayer-above')||/^g-y\d*title$/.test(node.getAttribute('class')))
        svg.append(node.cloneNode(true));
    }
    gutter.append(svg);
    current.rows.forEach((row,index)=>{
      const axis=layout[axisName('yaxis',index)];
      const heading=document.createElement('div');
      heading.className='summary-row-caption';
      heading.style.top=(axis._offset-58)+'px';
      heading.innerHTML=`<strong>${escape(row.title)}</strong><span>${escape(row.detail)}</span>`;
      captions.append(heading);
      if(!row.count) {
        const empty=document.createElement('div');
        empty.className='summary-empty-caption';
        empty.style.top=(axis._offset+axis._length/2)+'px';
        empty.textContent=row.empty;
        captions.append(empty);
      }
    });
  }

  function positionPanelScrollbars() {
    const holder=select('summary-panel-scrollbars'),graph=select('summary-chart');
    const viewport=select('summary-chart-viewport');
    holder.hidden=current.mode!=='scroll';
    if(holder.hidden||!graph._fullLayout?._size) return;
    if(holder.children.length!==current.rows.length) {
      holder.replaceChildren(...current.rows.map((row,index)=>{
        const bar=document.createElement('input');
        bar.type='range';bar.min='0';bar.step='1';bar.value='0';
        bar.className='summary-panel-scrollbar';bar.dataset.panel=index;
        bar.setAttribute('role','scrollbar');
        bar.setAttribute('aria-label',`Scroll all variable graphs horizontally from ${row.title}`);
        bar.setAttribute('aria-orientation','horizontal');
        bar.setAttribute('aria-controls','summary-chart-viewport');
        bar.addEventListener('input',()=>{
          if(current.mode!=='scroll') return;
          viewport.scrollLeft=Number(bar.value);
          hideTooltip();controls();
        });
        return bar;
      }));
    }
    const layout=graph._fullLayout,maximum=viewport.scrollWidth-viewport.clientWidth;
    [...holder.children].forEach((bar,index)=>{
      const axis=layout[axisName('yaxis',index)];
      let top=axis._offset+axis._length+4;
      if(index===current.rows.length-1) {
        const title=graph.querySelector('.x6title');
        const titleBottom=title?title.getBoundingClientRect().bottom-select('summary-chart-frame').getBoundingClientRect().top:top+40;
        top=Math.max(top+30,titleBottom+8);
      }
      bar.style.top=top+'px';bar.style.left=layout.margin.l+'px';bar.style.right=layout.margin.r+'px';
      bar.style.width=Math.max(0,viewport.clientWidth-layout.margin.l-layout.margin.r)+'px';
      bar.max=maximum;
      // Keep the visible thumb proportional to the viewport and always drawn,
      // including systems that automatically hide native overflow scrollbars.
      bar.style.setProperty('--thumb-width',Math.max(24,bar.clientWidth*viewport.clientWidth/viewport.scrollWidth)+'px');
    });
  }

  function controls() {
    const viewport=select('summary-chart-viewport'),slider=select('summary-scroll');
    const fit=current.mode==='fit';
    const maximum=Math.max(0,viewport.scrollWidth-viewport.clientWidth);
    slider.max=maximum;slider.value=Math.round(viewport.scrollLeft);slider.disabled=fit||maximum===0;
    select('summary-fit-year').setAttribute('aria-pressed',String(fit));
    select('summary-enable-scroll').setAttribute('aria-pressed',String(!fit));
    select('summary-mode-description').textContent=fit
      ? `All ${DAYS} days of ${current.year} fit across the chart width, from January to December.`
      : `All ${DAYS} days of ${current.year} are plotted on one wide chart. Scroll horizontally from January to December.`;
    select('summary-scroll-hint').textContent=`All ${DAYS} days stay on the chart. Use the top control, a small scrollbar under any variable, or swipe left and right.`;
    select('summary-prev').parentElement.hidden=fit;
    select('summary-navigator').hidden=fit;
    select('summary-prev').disabled=viewport.scrollLeft<=1;
    select('summary-next').disabled=viewport.scrollLeft>=maximum-1;
    const graph=select('summary-chart');
    if(graph._fullLayout) {
      const layout=graph._fullLayout,plotWidth=layout.xaxis._length;
      const first=Math.max(0,Math.min(DAYS-1,Math.floor(viewport.scrollLeft/plotWidth*DAYS)));
      const last=Math.max(first,Math.min(DAYS-1,Math.ceil((viewport.scrollLeft+viewport.clientWidth-layout.margin.l)/plotWidth*DAYS)-1));
      const label=`Visible part: ${displayDate(START+first*DAY)} — ${displayDate(START+last*DAY)}. The chart contains the full year.`;
      select('summary-visible-dates').textContent=label;
      slider.setAttribute('aria-valuetext',label);
    }
    for(const bar of select('summary-panel-scrollbars').children) {
      bar.max=maximum;bar.value=Math.round(viewport.scrollLeft);
      bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax',String(maximum));
      bar.setAttribute('aria-valuenow',String(Math.round(viewport.scrollLeft)));
      bar.setAttribute('aria-valuetext',slider.getAttribute('aria-valuetext')||`Full year ${current.year}`);
    }
    updateDateCursor();
  }

  async function resizeChart() {
    const graph=select('summary-chart');
    if(current.rendering||!graph.data||!graph._fullLayout?._size||select('summary-view').hidden||select('populated').hidden) return;
    hideTooltip();
    const width=chartWidth();
    graph.style.width=width+'px';
    const update={width,autosize:false,annotations:annotations(current.rows)};
    for(let index=0;index<6;index++) {
      update[`${axisName('xaxis',index)}.range`]=range();
      update[`${axisName('xaxis',index)}.tickvals`]=ticks();
    }
    await Plotly.relayout(graph,update);
    pinAxes();controls();
  }

  async function setMode(mode) {
    current.mode=mode;
    select('summary-chart-viewport').scrollLeft=0;
    await resizeChart();
  }

  function bind() {
    if(current.bound) return;
    current.bound=true;
    const graph=select('summary-chart'),viewport=select('summary-chart-viewport');
    graph.addEventListener('pointerleave',hideTooltip);
    graph.on('plotly_relayout',hideTooltip);
    graph.addEventListener('pointermove',moveCrosshair);
    graph.addEventListener('pointerdown',moveCrosshair);
    // Plotly consumes the native DOM dblclick; its own event still fires with
    // default double-click zoom disabled. Pointer-down selected the date first.
    graph.on('plotly_doubleclick',lockDate);
    window.addEventListener('scroll',hideTooltip,true);
    window.addEventListener('resize',()=>{
      clearTimeout(current.resizeTimer);
      current.resizeTimer=setTimeout(()=>resizeChart().catch(console.error),80);
    });
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape') {hideTooltip();if(current.locked) unlockDate();}
    });
    document.addEventListener('pointerdown',event=>{if(!event.target.closest('#summary-chart')) hideTooltip();});
    viewport.addEventListener('scroll',()=>{hideTooltip();controls();});
    select('summary-scroll').oninput=event=>{viewport.scrollLeft=Number(event.target.value);controls();};
    select('summary-fit-year').onclick=()=>setMode('fit').catch(console.error);
    select('summary-enable-scroll').onclick=()=>setMode('scroll').catch(console.error);
    select('summary-prev').onclick=()=>{viewport.scrollLeft-=viewport.clientWidth*.8;controls();};
    select('summary-next').onclick=()=>{viewport.scrollLeft+=viewport.clientWidth*.8;controls();};
    select('summary-lock-date').onclick=()=>{
      if(current.locked) unlockDate();
      else if(current.selectedDate) {lockDate();hideTooltip();}
    };
    select('summary-clear-date').onclick=()=>{current.selectedDate=null;current.locked=false;hideTooltip();updateDateCursor();};
    select('summary-year').onchange=event=>{
      current.year=Number(event.target.value);current.selectedDate=null;current.locked=false;
      viewport.scrollLeft=0;
      render(current.data,{refreshAvailability:false}).catch(console.error);
    };
  }

  async function render(data,{refreshAvailability=true}={}) {
    configureYear(data);
    select('summary-year').disabled=true;
    const {rows,traces,inflow,ffd,rain}=tracks(data);
    hideTooltip();
    current.hoverData={wapda:groupByDate(inflow),ffd:groupByDate(ffd),rain:groupByDate(rain),
      irsa:groupByDate(inYear(data.irsa)),peaks:groupByDate(inYear(data.peaks))};
    const number=value=>value.toLocaleString('en-US');
    const metrics=[
      ['WAPDA inflow',number(inflow.length),`${number(inflow.filter(row=>row.eligible).length)} eligible · ${inflow.filter(row=>!row.eligible).length} withheld`],
      ['FFD bulletins',number(ffd.length),`${new Set(ffd.map(row=>row.date)).size} printed dates · inflow + outflow`],
      ['Catchment precipitation',number(rain.filter(row=>row.value!==null).length),'Daily area averages · source values on hold'],
      ['Feature year',String(current.year),'01 January–31 December · saved readings only'],
    ];
    select('summary-metrics').innerHTML=metrics.map(([label,value,note])=>`<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-foot">${note}</div></div>`).join('');
    const width=chartWidth();
    select('summary-chart').style.width=width+'px';
    const layout={
      width,autosize:false,height:1480,paper_bgcolor:'transparent',plot_bgcolor:'transparent',
      margin:{l:86,r:22,t:82,b:68},showlegend:false,hovermode:'closest',dragmode:false,
      font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},
      hoverlabel:{bgcolor:'#172318',bordercolor:'#65734b',font:{color:'#f3e4bd',size:11}},
      annotations:[],bargap:.08,uirevision:`marala-summary-${current.year}`,
    };
    rows.forEach((row,index)=>{
      const top=1-index/rows.length;
      const bottom=top-1/rows.length+PANEL_GAP;
      layout[axisName('xaxis',index)]={type:'date',domain:[0,1],anchor:axisName('y',index),
        matches:index===rows.length-1?undefined:'x6',range:range(),fixedrange:true,showticklabels:index===0||index===rows.length-1,side:index===0?'top':'bottom',
        gridcolor:'rgba(190,211,178,.10)',zeroline:false,tickformat:'%d %b',tickfont:{size:10},tickmode:'array',tickvals:ticks(),
        title:index===rows.length-1?{text:`Date · ${current.year}`,font:{size:12}}:undefined};
      layout[axisName('yaxis',index)]={domain:[bottom,top],anchor:axisName('x',index),
        title:{text:row.unit,font:{size:10}},fixedrange:true,zeroline:false,
        gridcolor:'rgba(190,211,178,.10)',tickfont:{size:10},automargin:true,
        ...(!row.count?{range:[0,1],showticklabels:false}:{rangemode:'tozero'})};
    });
    current.rows=rows;
    layout.annotations=annotations(rows);
    current.rendering=true;
    try {
      await Plotly.react('summary-chart',traces,layout,{responsive:true,displaylogo:false,scrollZoom:false,doubleClick:false,
        modeBarButtons:[['toImage']],toImageButtonOptions:{format:'png',filename:`marala_summary_${current.year}`,scale:2}});
    } finally {current.rendering=false;select('summary-year').disabled=false;}
    bind();
    pinAxes();
    controls();
    if(refreshAvailability) await window.FloodAvailability.render(data);
  }

  return {render};
})();
