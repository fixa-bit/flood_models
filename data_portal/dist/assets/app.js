'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => Number(n ?? 0).toLocaleString('en-US');
const pct = n => `${(Number(n) * 100).toFixed(1)}%`;
const size = n => n >= 1048576 ? `${(n/1048576).toFixed(1)} MB` : `${(n/1024).toFixed(1)} KB`;
const nice = s => s.replace(/_/g,' ').replace(/\b\w/g, c=>c.toUpperCase());
const colors = {teal:'#75d0ac',amber:'#efb35e',navy:'#8db9df',purple:'#c6abd8',red:'#ed9f83',grey:'#263126'};
const state = {data:null, case:'riverine', view:'overview', fileCategory:'all', ledgerPage:0, map:null,grid:null,rivers:null};
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5000);}
function metric(label,value,foot,icon='◫'){return `<div class="metric"><div class="metric-label">${esc(label)}<span class="metric-icon" aria-hidden="true">${icon}</span></div><div class="metric-value">${esc(value)}</div><div class="metric-foot">${foot}</div></div>`;}
function pill(text,type=''){return `<span class="pill ${type}">${esc(text)}</span>`;}
function filtered(rows){const from=$('#from-date').value,to=$('#to-date').value;return rows.filter(r=>(!from||r.date>=from)&&(!to||r.date<=to));}
function plot(id,traces,layout={}){
  if(!window.Plotly)throw Error('The chart library could not load. Reload the portal.');
  const standard={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},margin:{l:62,r:23,t:28,b:44},
    xaxis:{gridcolor:'rgba(190,211,178,.09)',linecolor:'#3d4b34',showline:false,zeroline:false,tickfont:{size:9},type:'date',automargin:true},
    yaxis:{gridcolor:'rgba(190,211,178,.09)',zeroline:false,tickfont:{size:9},automargin:true},
    hoverlabel:{bgcolor:'#172318',bordercolor:'#65734b',font:{color:'#f3e4bd',size:11}},hovermode:'closest',
    legend:{orientation:'h',x:0,y:1.15,font:{size:9}},showlegend:false,dragmode:'zoom'};
  const merged={...standard,...layout,xaxis:{...standard.xaxis,...layout.xaxis},yaxis:{...standard.yaxis,...layout.yaxis}};
  if(traces.every(t=>!t.x?.length&&!t.z?.length&&!t.values?.length))merged.annotations=[{text:'No observations in this period',showarrow:false,x:.5,y:.5,xref:'paper',yref:'paper',font:{size:12,color:'#bcc6a7'}}];
  return Plotly.react(id,traces,merged,{responsive:true,displaylogo:false,scrollZoom:false,modeBarButtonsToRemove:['lasso2d','select2d'],toImageButtonOptions:{format:'png',filename:`marala_${id}`,scale:2}});
}
function withGaps(rows,key){const sorted=[...rows].sort((a,b)=>a.date.localeCompare(b.date));const out=[];let previous=null;for(const r of sorted){if(previous&&Date.parse(r.date)-Date.parse(previous)>86400000)out.push({date:new Date(Date.parse(previous)+86400000).toISOString().slice(0,10),[key]:null});out.push(r);previous=r.date;}return out;}
function line(rows,key,name,color,extra={}){const rs=withGaps(rows,key);return {x:rs.map(r=>r.date),y:rs.map(r=>r[key]),name,type:'scatter',mode:'lines',line:{color,width:1.8},connectgaps:false,hovertemplate:`%{x|%d %b %Y}<br>${esc(name)}: %{y:,.1f}<extra></extra>`,...extra};}

async function loadData(){
  $('#reload').disabled=true;
  try{
    const response=await fetch(`data/portal.json?checked=${Date.now()}`,{cache:'no-store'});
    if(!response.ok)throw Error(`Data snapshot returned ${response.status}`);
    const d=await response.json();if(d.schema_version!==1)throw Error('Unsupported snapshot version');state.data=d;
    $('#snapshot-time').textContent=new Date(d.built_utc).toLocaleString('en-GB',{timeZone:'Asia/Karachi',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' PKT';
    const years=[...new Set([...d.marala.inflow,...d.marala.precipitation].map(r=>r.date.slice(0,4)))].sort();
    const selected=$('#year').value||'2024';$('#year').innerHTML='<option value="all">All years</option>'+years.map(y=>`<option value="${y}">${y}</option>`).join('')+'<option value="custom">Custom dates</option>';$('#year').value=selected;
    $('#event').innerHTML=d.marala.events.map(e=>`<option value="${e.id}">${esc(e.label)}</option>`).join('');$('#event').value='2024';
    $('#load-error').hidden=true;renderCases();await render();
  }catch(e){$('#load-error').textContent=`Unable to load the portal. ${e.message}. Start it with the supplied launch script or a local HTTP server.`;$('#load-error').hidden=false;}
  finally{$('#reload').disabled=false;}
}
function renderCases(){const icons={riverine:'≋',flash:'ϟ',seasonal:'◷',urban:'▥'};$('#case-nav').innerHTML=state.data.cases.map(c=>`<button class="case-button ${c.id===state.case?'active':''}" data-case="${c.id}" aria-pressed="${c.id===state.case}"><span class="case-icon" aria-hidden="true">${icons[c.id]}</span>${esc(c.label)}<span class="case-dot" title="${c.status==='collected'?'Data collected':'Not collected'}"></span></button>`).join('');$$('[data-case]').forEach(b=>b.onclick=()=>{state.case=b.dataset.case;renderCases();render();$('#sidebar').classList.remove('open');$('#menu-toggle').setAttribute('aria-expanded','false');});}
async function render(){
  if(!state.data)return;
  const c=state.data.cases.find(c=>c.id===state.case);$('#case-breadcrumb').textContent=c.label;
  const view=location.hash.slice(1)||'overview';state.view=['overview','sources','quality','catchment','library'].includes(view)?view:'overview';
  $$('[data-view]').forEach(a=>a.classList.toggle('active',a.dataset.view===state.view));
  const titles={overview:['Flood data observatory','Trace the sources. Inspect the gaps. Explore the records.'],sources:['Sources & provenance','Every collected source, its purpose and its saved evidence.'],quality:['Integrity & quality','See what passed, what is uncertain, and what needs review.'],catchment:['Catchment explorer','The upstream area behind Marala’s precipitation and inflow.'],library:['Data library','Explore and download the records behind the charts.']};
  $('#page-title').textContent=titles[state.view][0];$('#page-subtitle').textContent=titles[state.view][1];
  $('#station').disabled=state.case!=='riverine';const populated=state.case==='riverine'&&$('#station').value==='marala'&&$('#horizon').value==='short';
  $('#populated').hidden=!populated;$('#empty-state').hidden=populated;
  if(!populated){renderEmpty(c);return;}
  $$('.view').forEach(v=>v.hidden=v.id!==`${state.view}-view`);
  if(state.view==='overview')await renderOverview();
  if(state.view==='sources')renderSources();
  if(state.view==='quality')await renderQuality();
  if(state.view==='catchment')await renderCatchment();
  if(state.view==='library')renderLibrary();
}
function renderEmpty(c){
  const isJassar=state.case==='riverine'&&$('#station').value==='jassar';
  const label=isJassar?'Ravi · Jassar':c.label;
  const long=$('#horizon').value==='long';
  $('#empty-state').innerHTML=`<section class="empty-panel"><div class="empty-symbol" aria-hidden="true">${isJassar?'≋':'◫'}</div><div class="eyebrow">COLLECTION STATUS · NOT STARTED</div><h2>${esc(label)}${long?' · long range':''}</h2><p>No collected dataset is available for this model selection. Its workspace folders are ready; source coverage, integrity checks and plots will appear after data is collected and this portal snapshot is rebuilt.</p><div class="empty-steps"><span>1 · Collect source data</span><span>2 · Check and prepare</span><span>3 · Refresh the portal</span></div><p>Charts are shown only for datasets present in the project.</p><button class="button" id="back-marala">Explore collected Marala data →</button></section>`;
  $('#back-marala').onclick=()=>{state.case='riverine';$('#station').value='marala';$('#horizon').value='short';renderCases();render();};
}
async function renderOverview(){
  const m=state.data.marala,base=m.quality.baseline,rain=m.rainfall_report;
  $('#overview-metrics').innerHTML=metric('Eligible daily inflow',fmt(base.eligible_daily_training_rows),`${fmt(base.rows)} source dates · <strong>7 withheld</strong>`,'≋')+metric('Catchment precipitation',fmt(rain.valid_daily_rows),`Complete UTC days · <strong>100% spatial coverage</strong>`,'⋮')+metric('Source groups',state.data.sources.length,'Public providers, references and source evidence','⌁')+metric('Original files checked',fmt(state.data.integrity.counts.match),`${fmt(state.data.integrity.files.length)} checksum comparisons · <strong>local snapshot</strong>`,'✓');
  if(m.feature_coverage_audit?.rainfall_quality_blocked)$('#research-note').innerHTML='<span class="notice-icon">!</span><div><strong>Rainfall is not cleared for training.</strong><p>Dates match the WAPDA record, but saved long-range NASA responses disagree with independent short-period checks. Sample: 851.28 mm saved versus 35.47 mm from both a daily request and summed hourly values. Review the feature coverage audit before training.</p></div><a href="downloads/marala_feature_coverage_audit.json" target="_blank">Open audit ?</a>';
  const q=filtered(m.inflow);const excluded=q.filter(r=>!r.eligible);const traces=[line(q,'value','Eligible WAPDA inflow',colors.teal),{type:'scatter',mode:'markers',x:excluded.map(r=>r.date),y:excluded.map(r=>r.source_value),name:'Withheld WAPDA source value',marker:{color:colors.amber,size:8,symbol:'circle-open',line:{width:2}},text:excluded.map(r=>r.flag),hovertemplate:'%{x|%d %b %Y}<br>Source value: %{y:,.0f} cusecs<br>%{text}<extra>Withheld</extra>'}];
  if($('#show-ffd').checked){const ff=filtered(m.ffd);traces.push(line(ff.filter(r=>!r.flag),'inflow','FFD 06:00 inflow',colors.navy,{line:{color:colors.navy,width:1.1,dash:'dot'},opacity:.8}));const bad=ff.filter(r=>r.flag);traces.push({type:'scatter',mode:'markers',x:bad.map(r=>r.date),y:bad.map(r=>r.inflow),name:'FFD date conflict',marker:{color:colors.red,size:7,symbol:'diamond-open'},text:bad.map(r=>'Archive date: '+r.archive_date),hovertemplate:'Printed %{x|%d %b %Y}<br>%{y:,.0f} cusecs<br>%{text}<extra>Date conflict</extra>'});}
  const rr=filtered(m.precipitation);
  const highRain=rr.filter(r=>r.value!==null&&r.value>=m.rainfall_screening.threshold_mm_day);
  const rainMarkers={type:'scatter',mode:'markers',x:highRain.map(r=>r.date),y:highRain.map(r=>r.value),marker:{color:colors.amber,size:5,symbol:'circle-open'},hovertemplate:'%{x|%d %b %Y}<br>%{y:.3f} mm/day<extra>Review high precipitation</extra>'};
  const tasks=[plot('discharge-chart',traces,{yaxis:{title:{text:'Inflow (cusecs)',font:{size:9}}}}),plot('rain-chart',[{type:'bar',x:rr.map(r=>r.date),y:rr.map(r=>r.value),marker:{color:colors.navy,opacity:.75},hovertemplate:'%{x|%d %b %Y} · UTC day<br>%{y:.3f} mm/day<extra>Catchment mean</extra>'},rainMarkers],{bargap:.1,yaxis:{title:{text:'Precipitation (mm/day)',font:{size:9}}}})];
  const selectedYear=$('#year').value;
  let rows=[];
  for(const year of [...new Set([...m.inflow,...m.precipitation].map(r=>Number(r.date.slice(0,4))))].sort()){
    if(selectedYear!=='all'&&selectedYear!=='custom'&&year!==Number(selectedYear))continue;
    for(const [label,series] of [['Inflow',m.monthly.inflow],['Precip.',m.monthly.precipitation]]){
      const months=Array.from({length:12},(_,i)=>series.find(r=>r.year===year&&r.month===i+1));
      rows.push({label:`${year} · ${label}`,z:months.map(x=>x?.fraction??null),text:months.map(x=>x&&x.expected?`${x.valid}/${x.expected} usable days`:'Outside collected span')});
    }
  }
  if(rows.length>10)$('#coverage-chart').style.height='420px';else $('#coverage-chart').style.height='270px';
  tasks.push(plot('coverage-chart',[{type:'heatmap',x:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],y:rows.map(r=>r.label),z:rows.map(r=>r.z),text:rows.map(r=>r.text),hovertemplate:'%{y} · %{x}<br>%{text}<extra></extra>',zmin:0,zmax:1,colorscale:[[0,'#f5e5c0'],[.7,'#b8d8ae'],[1,'#438767']],xgap:3,ygap:6,showscale:false,hoverongaps:false}],{margin:{l:98,r:20,t:25,b:40},xaxis:{type:'category',showgrid:false},yaxis:{type:'category',autorange:'reversed',showgrid:false},plot_bgcolor:'#172014'}));
  tasks.push(plot('distribution-chart',[{type:'histogram',x:q.filter(r=>r.eligible).map(r=>r.value),nbinsx:35,marker:{color:'#7eaf8b',line:{color:'#fff',width:1}},hovertemplate:'Flow bin %{x}<br>%{y} days<extra></extra>'}],{xaxis:{type:'linear',title:{text:'Inflow (cusecs)',font:{size:9}}},yaxis:{title:{text:'Days',font:{size:9}}},bargap:.08}));
  tasks.push(plot('irsa-chart',[line(m.irsa,'inflow','Mean upstream',colors.teal),line(m.irsa,'outflow','Mean downstream',colors.navy)],{showlegend:true,yaxis:{title:{text:'Mean discharge (cusecs)',font:{size:9}}}}));
  tasks.push(plot('peaks-chart',[{type:'scatter',mode:'markers',x:m.peaks.map(r=>r.date),y:m.peaks.map(r=>r.value),marker:{color:colors.purple,size:7},text:m.peaks.map(r=>r.level),hovertemplate:'%{x|%d %b %Y}<br>%{y:,.0f} cusecs<br>Published class: %{text}<extra>Selected event peak</extra>'}],{yaxis:{title:{text:'Peak (cusecs)',font:{size:9}}}}));
  tasks.push(renderEvent());await Promise.all(tasks);
}
async function renderEvent(){const m=state.data.marala;const event=m.events.find(e=>e.id===$('#event').value)||m.events[0];if(!event)return;const q=m.inflow.filter(r=>r.date>=event.start&&r.date<=event.end),r=m.precipitation.filter(r=>r.date>=event.start&&r.date<=event.end);return plot('event-chart',[{type:'bar',x:r.map(x=>x.date),y:r.map(x=>x.value),name:'Precipitation',yaxis:'y2',marker:{color:'#c5dce8',opacity:.7},hovertemplate:'%{x|%d %b %Y}<br>Precipitation %{y:.2f} mm/day<extra>UTC day</extra>'},line(q,'value','Eligible inflow',colors.teal)],{showlegend:true,margin:{l:56,r:52,t:24,b:45},yaxis:{title:{text:'Inflow (cusecs)',font:{size:9}}},yaxis2:{overlaying:'y',side:'right',showgrid:false,title:{text:'mm/day',font:{size:9}},rangemode:'tozero'},annotations:[{x:event.date,y:event.value,text:'Annual daily maximum',ax:0,ay:-30,font:{size:9,color:'#c8d7ad'},arrowcolor:'#8ba784'}]});}
function renderSources(){
  const term=$('#source-search').value.toLowerCase();const sources=state.data.sources.filter(s=>(s.name+' '+s.purpose+' '+s.note).toLowerCase().includes(term));
  $('#source-cards').innerHTML=sources.map(s=>{const bad=(s.counts.mismatch||0)+(s.counts.missing||0)+(s.counts.conflicting_claims||0);return `<article class="source-card"><div class="source-card-header"><span class="provider-mark">${esc(s.id==='nasa_power'?'NASA':s.name.slice(0,3).toUpperCase())}</span>${pill(bad?'Needs review':'Hashes match',bad?'red':'green')}</div><div><h3>${esc(s.name)}</h3><div class="purpose">${esc(s.purpose)}</div></div><p class="source-note">${esc(s.note)}</p><div class="source-facts"><span>Checked files<strong>${fmt(s.files)}</strong></span><span>Source data size<strong>${size(s.bytes)}</strong></span><span>Matched hashes<strong>${fmt(s.counts.match||0)}</strong></span></div><a class="source-link" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open provider source ↗</a><details><summary>${fmt(s.links.length)} collected source links</summary><div class="more-links">${s.links.map(u=>`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`).join('')}</div></details></article>`;}).join('')||'<p class="card-note">No matching sources.</p>';
}
async function renderQuality(){
  const d=state.data,m=d.marala,ic=d.integrity.counts,b=m.quality.baseline;
  const fail=(ic.mismatch||0)+(ic.missing||0)+(ic.conflicting_claims||0);
  $('#quality-metrics').innerHTML=metric('Checksum exceptions',fmt(fail),`${fmt(ic.match)} files match saved receipts`,fail?'!':'✓')+metric('Withheld WAPDA dates',fmt(b.withheld_dates.length),'One zero and six source disagreements','!')+metric('Unconfirmed reading time',fmt(b.unknown_time_rows),'WAPDA dates · 1 companion-confirmed time','◷')+metric('Catchment checks',`${Object.values(m.catchment.checks).filter(Boolean).length} / ${Object.keys(m.catchment.checks).length}`,'Source and geometry checks · research boundary','◇');
  const layers=[['File integrity',`${fmt(ic.match)} local files match their saved checksum claims.`,true],['Rainfall preparation',`${fmt(m.rainfall_report.valid_daily_rows)} complete days; full catchment area. A missing cell leaves the day blank.`,true],['Precipitation plausibility',`${fmt(m.rainfall_screening.count)} days exceed the advisory 100 mm/day screen; maximum ${fmt(m.rainfall_screening.maximum?.value)} mm/day. Review units and source plausibility. This is not an official invalid-data threshold.`,false],['Discharge consistency',`${b.exact_ffd_value_matches}/${b.ffd_comparisons} overlapping FFD values match WAPDA. Seven WAPDA days remain withheld.`,false],['Observation times',`${fmt(b.unknown_time_rows)} WAPDA dates lack an individually confirmed reading hour.`,false],['Boundary verification','Station location, area and geometry checks passed; no agency or field certification.',false]];
  if(m.feature_coverage_audit?.rainfall_quality_blocked)layers.unshift(['Rainfall source consistency','Training blocked: independent short-period daily and hourly checks disagree with saved long-range responses. Temporal coverage is complete, but rainfall values need to be revalidated.',false]);
  $('#verification-layers').innerHTML=layers.map(([title,note,ok])=>`<div class="verification-item"><span class="check-icon ${ok?'':'warn'}">${ok?'✓':'!'}</span><div><strong>${esc(title)}</strong>${esc(note)}</div></div>`).join('');
  $('#review-rows').innerHTML=m.reviews.map(r=>`<tr><td class="quality-date"><strong>${esc(r.date)}</strong><div class="cell-note">Withheld</div></td><td>${pill(r.issue==='zero_needs_review'?'Zero needs review':'Source disagreement','amber')}</td><td>${fmt(r.wapda_inflow_cusecs)}</td><td>${r.ffd_inflow_cusecs?fmt(r.ffd_inflow_cusecs):'—'}</td><td><strong>${esc(r.review_id)}</strong><div class="cell-note">${esc(r.review_notes)}</div><a href="${esc(r.wapda_url)}" target="_blank" rel="noopener">WAPDA ↗</a>${r.ffd_url?`<a href="${esc(r.ffd_url)}" target="_blank" rel="noopener">FFD original ↗</a>`:''}</td></tr>`).join('');
  $('#recent-coverage').innerHTML=Object.entries(m.quality.recent_coverage).map(([year,r])=>{const c=r.ffd_status_counts,valid=c.available_unique_0600||0,conflict=c.date_or_duplicate_conflict||0,missing=c.missing||0,n=r.calendar_days_through_as_of;return `<div class="coverage-year"><h3>${esc(year)} · ${n} calendar days checked</h3><div class="coverage-bar"><span style="width:${100*valid/n}%;background:#79a679"></span><span style="width:${100*conflict/n}%;background:#d6b569"></span><span style="width:${100*missing/n}%;background:#e8eadd"></span></div><div class="coverage-caption"><span>${valid} unique 06:00 readings</span><span>${conflict} conflicts</span><span>${missing} missing</span></div></div>`;}).join('');
  renderLedger();
  const time=Object.entries(m.time_status_counts);const icEntries=[['Match',ic.match||0,colors.teal],['Mismatch',ic.mismatch||0,colors.red],['Missing file',ic.missing||0,colors.amber],['Conflicting claims',ic.conflicting_claims||0,colors.purple]].filter(x=>x[1]);
  await Promise.all([plot('integrity-chart',[{type:'pie',labels:icEntries.map(x=>x[0]),values:icEntries.map(x=>x[1]),marker:{colors:icEntries.map(x=>x[2]),line:{color:'#fff',width:3}},hole:.76,textinfo:'none',hovertemplate:'%{label}: %{value} files<extra></extra>'}],{margin:{l:20,r:20,t:15,b:15},annotations:[{text:`<b>${fmt(d.integrity.files.length)}</b><br><span style="font-size:10px">checked files</span>`,xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false,font:{size:27,color:'#e6d3a2'}}]}),plot('time-chart',[{type:'bar',orientation:'h',x:time.map(x=>x[1]),y:time.map(x=>({not_given_for_individual_record:'Time not stated',explicit_in_source:'Explicit in bulletin',confirmed_by_companion_report:'Companion confirmed',averaging_period_bounds_not_stated:'Mean bounds unstated'}[x[0]]||nice(x[0]))),marker:{color:['#d0b278',colors.teal,colors.navy,colors.purple]},hovertemplate:'%{y}<br>%{x:,.0f} catalog rows<extra></extra>'}],{margin:{l:150,r:25,t:20,b:35},xaxis:{type:'linear'},yaxis:{type:'category',showgrid:false}})]);
}
function renderLedger(){const term=$('#integrity-search').value.toLowerCase();const rows=state.data.integrity.files.filter(r=>(r.path+' '+r.provider+' '+r.status).toLowerCase().includes(term));const pageSize=14;state.ledgerPage=Math.max(0,Math.min(state.ledgerPage,Math.ceil(rows.length/pageSize)-1));const page=rows.slice(state.ledgerPage*pageSize,(state.ledgerPage+1)*pageSize);$('#integrity-ledger').innerHTML=page.map(r=>`<details><summary>${pill(r.status==='match'?'Match':nice(r.status),r.status==='match'?'green':'red')}<span class="ledger-name">${esc(r.path.split('/').slice(-2).join('/'))}</span><span>${esc(r.provider)}</span></summary><div class="hash-content">Path: ${esc(r.path)}<br>Expected SHA-256: <code>${esc(r.expected_sha256.join(', '))}</code><br>Actual SHA-256: <code>${esc(r.actual_sha256||'File missing')}</code>${r.source_urls.length?`<br><a href="${esc(r.source_urls[0])}" target="_blank" rel="noopener">Original source ↗</a>`:''}</div></details>`).join('')||'<p class="card-note">No matching files.</p>';$('#ledger-pages').innerHTML=`<button id="ledger-prev" ${state.ledgerPage===0?'disabled':''}>← Previous</button><span>${rows.length?state.ledgerPage*pageSize+1:0}–${Math.min(rows.length,(state.ledgerPage+1)*pageSize)} of ${rows.length} files</span><button id="ledger-next" ${(state.ledgerPage+1)*pageSize>=rows.length?'disabled':''}>Next →</button>`;$('#ledger-prev').onclick=()=>{state.ledgerPage--;renderLedger();};$('#ledger-next').onclick=()=>{state.ledgerPage++;renderLedger();};}

async function renderCatchment(){
  const m=state.data.marala,c=m.catchment,r=m.rainfall_report;
  $('#catchment-metrics').innerHTML=metric('Upstream catchment',fmt(Math.round(c.area_km2_geodesic)),'km² · WGS84 geodesic area','◇')+metric('Precipitation grid',r.grid_cells,'Catchment-intersecting source cells','▦')+metric('Spatial coverage',pct(r.spatial_coverage_fraction),'Full saved catchment area','✓')+metric('Station location','32.67° N','74.46° E · JICA / PMD inventory','⌖');
  $('#catchment-checks').innerHTML=Object.entries(c.checks).map(([name,pass])=>`<div class="verification-item"><span class="check-icon ${pass?'':'warn'}">${pass?'✓':'!'}</span><div><strong>${esc(nice(name).replace('Pmd','PMD').replace('Jica','JICA').replace('Iou','IoU'))}</strong></div></div>`).join('');
  if(!state.map){const urls=['downloads/marala_upstream_catchment.geojson','downloads/marala_rainfall_catchment_cells.geojson','downloads/marala_upstream_rivers.geojson'];const values=await Promise.all(urls.map(async u=>{const response=await fetch(u);if(!response.ok)throw Error(`Map file ${u}: ${response.status}`);return response.json();}));[state.map,state.grid,state.rivers]=values;}
  const traces=[];const rings=geometry=>geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
  for(const polygon of rings(state.map.features[0].geometry)){const coords=polygon[0];traces.push({type:'scatter',mode:'lines',x:coords.map(c=>c[0]),y:coords.map(c=>c[1]),line:{color:colors.teal,width:1.6},fill:'toself',fillcolor:'rgba(86,151,108,.15)',hoverinfo:'skip',name:'Catchment'});}
  const riverX=[],riverY=[];for(const f of state.rivers.features){for(const p of f.geometry.coordinates){riverX.push(p[0]);riverY.push(p[1]);}riverX.push(null);riverY.push(null);}traces.push({type:'scatter',mode:'lines',x:riverX,y:riverY,line:{color:'#7ca6bb',width:.7},hoverinfo:'skip',name:'Upstream network'});
  if($('#show-grid').checked){for(const f of state.grid.features){for(const polygon of rings(f.geometry)){const coords=polygon[0];traces.push({type:'scatter',mode:'lines',x:coords.map(c=>c[0]),y:coords.map(c=>c[1]),line:{color:'#c89f51',width:.85},fill:'toself',fillcolor:'rgba(201,164,88,0.035)',text:coords.map(()=>`${f.properties.cell_id}<br>Catchment area weight: ${pct(f.properties.area_weight)}`),hovertemplate:'%{text}<extra></extra>'});}}}
  traces.push({type:'scatter',mode:'markers+text',x:[74.46],y:[32.67],text:['Marala'],textposition:'bottom right',textfont:{color:'#f1be7a',size:12},marker:{color:'#b66d43',size:10,line:{width:2,color:'#fff'}},hovertemplate:'Marala · published coordinate<br>32.67 N, 74.46 E<extra>JICA / PMD</extra>'});
  const cells=state.grid.features.map(f=>f.properties).sort((a,b)=>b.area_weight-a.area_weight);
  await Promise.all([plot('map-chart',traces,{margin:{l:60,r:30,t:20,b:50},xaxis:{type:'linear',title:{text:'Longitude (° E)',font:{size:9}},range:[73.9,77.95]},yaxis:{type:'linear',title:{text:'Latitude (° N)',font:{size:9}},scaleanchor:'x',scaleratio:1.19,range:[31.98,34.32]},hovermode:'closest'}),plot('weights-chart',[{type:'bar',x:cells.map(c=>c.cell_id.replace('lat_','').replace('_lon_',', ')),y:cells.map(c=>100*c.area_weight),marker:{color:'#8caf7e'},hovertemplate:'Grid center %{x}<br>%{y:.4f}% of catchment area<extra></extra>'}],{margin:{l:50,r:20,t:20,b:88},xaxis:{type:'category',tickangle:-55,tickfont:{size:7}},yaxis:{title:{text:'Catchment weight (%)',font:{size:9}}}})]);
}
function renderLibrary(){
  $('#library-categories').innerHTML=['all','discharge','rainfall','catchment','metadata'].map(c=>`<button data-category="${c}" class="${c===state.fileCategory?'active':''}">${nice(c)}</button>`).join('');$$('[data-category]').forEach(b=>b.onclick=()=>{state.fileCategory=b.dataset.category;renderLibrary();});
  const term=$('#file-search').value.toLowerCase();const files=state.data.downloads.filter(f=>(state.fileCategory==='all'||f.category===state.fileCategory)&&(f.name+' '+f.path).toLowerCase().includes(term));
  $('#file-rows').innerHTML=files.map(f=>`<tr><td><strong>${esc(f.name)}</strong><div class="cell-note"><code>${esc(f.path)}</code></div><details><summary>SHA-256</summary><code>${esc(f.sha256)}</code></details></td><td>${pill(nice(f.category))}</td><td>${size(f.bytes)}</td><td>${f.url?`<a href="${esc(f.url)}" download>Download ↓</a><a href="${esc(f.url)}" target="_blank" rel="noopener">Open ↗</a>`:'<span class="cell-note">Large source-cell table available in the local project</span>'}</td></tr>`).join('')||'<tr><td colspan="4">No matching files.</td></tr>';
}
function applyYear(){const y=$('#year').value;if(y==='all'){$('#from-date').value='2016-03-01';$('#to-date').value='2026-10-22';}else if(y!=='custom'){$('#from-date').value=`${y}-01-01`;$('#to-date').value=`${y}-12-31`;if(state.data.marala.events.some(e=>e.id===y))$('#event').value=y;}render().catch(showRenderError);}
function showRenderError(error){console.error(error);toast(`Could not render this view: ${error.message}`);}
window.addEventListener('hashchange',()=>render().catch(showRenderError));
window.addEventListener('resize',()=>$$('.js-plotly-plot').filter(el=>el.offsetParent).forEach(el=>Plotly.Plots.resize(el)));
$('#reload').onclick=async()=>{await loadData();toast('Reloaded the saved data snapshot. New project data appears after rebuilding the portal.');};
$('#station').onchange=()=>render().catch(showRenderError);$('#horizon').onchange=()=>render().catch(showRenderError);$('#year').onchange=applyYear;
for(const id of ['#from-date','#to-date'])$(id).onchange=()=>{if($('#from-date').value>$('#to-date').value){toast('Choose a start date before the end date.');return;}$('#year').value='custom';render().catch(showRenderError);};
$('#reset-dates').onclick=()=>{$('#year').value='all';applyYear();};$('#show-ffd').onchange=()=>renderOverview().catch(showRenderError);$('#event').onchange=()=>renderEvent().catch(showRenderError);
$('#source-search').oninput=renderSources;$('#integrity-search').oninput=()=>{state.ledgerPage=0;renderLedger();};$('#file-search').oninput=renderLibrary;$('#show-grid').onchange=()=>renderCatchment().catch(showRenderError);
$('#menu-toggle').onclick=()=>{const open=$('#sidebar').classList.toggle('open');$('#menu-toggle').setAttribute('aria-expanded',String(open));};
$$('[data-view]').forEach(a=>a.addEventListener('click',()=>{$('#sidebar').classList.remove('open');$('#menu-toggle').setAttribute('aria-expanded','false');}));
loadData();
