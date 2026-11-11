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
let loadingSnapshot=false;
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

async function loadData({automatic=false}={}){
  if(loadingSnapshot)return;
  loadingSnapshot=true;
  $('#reload').disabled=true;
  try{
    const response=await fetch(`data/portal.json?checked=${Date.now()}`,{cache:'no-store'});
    if(!response.ok)throw Error(`Data snapshot returned ${response.status}`);
    const d=await response.json();if(d.schema_version!==1)throw Error('Unsupported snapshot version');state.data=d;
    if(window.FloodModels?.builtUtc())await window.FloodModels.refresh().catch(error=>console.warn('Model results not refreshed:',error.message));
    $('#snapshot-time').textContent=new Date(d.built_utc).toLocaleString('en-GB',{timeZone:'Asia/Karachi',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' PKT';
    const oldStation=$('#station').value||'marala';$('#station').innerHTML=(d.stations||[]).map(s=>`<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');$('#station').value=(d.stations||[]).some(s=>s.id===oldStation)?oldStation:'marala';
    const dailyInputs=d.marala.daily_inputs||[];
    const yearSet=new Set();for(const row of [...d.marala.inflow,...d.marala.precipitation])yearSet.add(row.date.slice(0,4));for(const series of dailyInputs)for(const row of series.rows)yearSet.add(row.date.slice(0,4));
    const years=[...yearSet].sort();
    const selected=$('#year').value||'2024';$('#year').innerHTML='<option value="all">All years</option>'+years.map(y=>`<option value="${y}">${y}</option>`).join('')+'<option value="custom">Custom dates</option>';$('#year').value=selected==='all'||selected==='custom'||years.includes(selected)?selected:'all';
    const oldEvent=$('#event').value;$('#event').innerHTML=d.marala.events.map(e=>`<option value="${e.id}">${esc(e.label)}</option>`).join('');$('#event').value=d.marala.events.some(e=>e.id===oldEvent)?oldEvent:(d.marala.events.at(-1)?.id||'');
    $('#load-error').hidden=true;renderCases();await render();
    if(automatic)toast('New data detected. The portal views and availability charts have been refreshed.');
  }catch(e){$('#load-error').textContent=`Unable to load the portal. ${e.message}. Start it with the supplied launch script or a local HTTP server.`;$('#load-error').hidden=false;}
  finally{loadingSnapshot=false;$('#reload').disabled=false;}
}
function renderCases(){const icons={riverine:'≋',flash:'ϟ',seasonal:'◷',urban:'▥'};$('#case-nav').innerHTML=state.data.cases.map(c=>`<button class="case-button ${c.id===state.case?'active':''}" data-case="${c.id}" aria-pressed="${c.id===state.case}"><span class="case-icon" aria-hidden="true">${icons[c.id]}</span>${esc(c.label)}<span class="case-dot" title="${c.status==='collected'?'Data collected':'Not collected'}"></span></button>`).join('');$$('[data-case]').forEach(b=>b.onclick=()=>{state.case=b.dataset.case;renderCases();render();$('#sidebar').classList.remove('open');$('#menu-toggle').setAttribute('aria-expanded','false');});}
async function render(){
  if(!state.data)return;
  const c=state.data.cases.find(c=>c.id===state.case);$('#case-breadcrumb').textContent=c.label;
  const [hashView,hashRange]=location.hash.slice(1).split('/');
  const view=hashView||'overview';state.view=['overview','summary','rainfall','sources','quality','catchment','library','models','analyzer'].includes(view)?view:'overview';
  if(['models','analyzer'].includes(state.view)&&['short','long'].includes(hashRange))$('#horizon').value=hashRange;
  $$('[data-view]').forEach(a=>a.classList.toggle('active',a.dataset.view===state.view));
  const titles={overview:['Flood data observatory','Trace the sources. Inspect the gaps. Explore the records.'],sources:['Sources & provenance','Every collected source, its purpose and its saved evidence.'],quality:['Integrity & quality','See what passed, what is uncertain, and what needs review.'],catchment:['Catchment explorer','The upstream area behind Marala’s precipitation and inflow.'],library:['Data library','Explore and download the records behind the charts.']};
  titles.summary=['Summary','Explore feature values and data availability with independent year selectors.'];
  titles.rainfall=['Rainfall sources','Explore every collected catchment rainfall series and its source coverage.'];
  titles.models=['Models','Accuracy, predictions and versions of every model, by station and forecast range.'];
  titles.analyzer=['Performance analyzer','How a model performs, and how it compares with a baseline or its earlier versions.'];
  $('#page-title').textContent=titles[state.view][0];$('#page-subtitle').textContent=titles[state.view][1];
  $('#filters').hidden=['summary','rainfall','models','analyzer'].includes(state.view);
  if(['models','analyzer'].includes(state.view)){
    $('#station').disabled=state.case!=='riverine';
    $('#populated').hidden=false;$('#empty-state').hidden=true;
    $$('.view').forEach(v=>v.hidden=v.id!==`${state.view}-view`);
    const stationId=$('#station').value,stationEntry=(state.data.stations||[]).find(s=>s.id===stationId);
    await window.FloodModels.render(state.view,{station:stationId,stationName:stationEntry?.name,caseId:state.case,caseLabel:c.label,horizon:$('#horizon').value,
      setRange:range=>{$('#horizon').value=range;history.replaceState(null,'',`#${state.view}/${range}`);render().catch(showRenderError);},
      setStation:id=>{$('#station').value=id;render().catch(showRenderError);},
      setCase:id=>{state.case=id;renderCases();render().catch(showRenderError);}});
    return;
  }
  $('#station').disabled=state.case!=='riverine';const station=(state.data.stations||[]).find(s=>s.id===$('#station').value);const populated=state.case==='riverine'&&Boolean(station)&&$('#horizon').value==='short';
  if(populated&&station.id!=='marala'){$('#populated').hidden=true;$('#empty-state').hidden=false;renderStationWorkspace(station);return;}
  $('#populated').hidden=!populated;$('#empty-state').hidden=populated;
  if(!populated){renderEmpty(c);return;}
  $$('.view').forEach(v=>v.hidden=v.id!==`${state.view}-view`);
  if(state.view==='overview')await renderOverview();
  if(state.view==='summary'){await window.FloodSummary.render(state.data.marala);renderStationFolderSummary(station);}
  if(state.view==='rainfall')await window.FloodRainfall.render(state.data.marala);
  if(state.view==='sources')renderSources();
  if(state.view==='quality')await renderQuality();
  if(state.view==='catchment')await renderCatchment();
  if(state.view==='library')renderLibrary();
}
function renderEmpty(c){
  const isJassar=state.case==='riverine'&&$('#station').value==='jassar';
  const label=isJassar?'Ravi · Jassar':c.label;
  const long=$('#horizon').value==='long';
  if(long&&state.case==='riverine'){
    $('#empty-state').innerHTML=`<section class="empty-panel"><div class="empty-symbol" aria-hidden="true">◫</div><div class="eyebrow">LONG RANGE · RESULTS ARE IN MODELS</div><h2>${esc(label)} · long range</h2><p>Long-range results are ready in Models: the 180-day Temporal Fusion Transformer, seasonal outlooks, the flood-peak model and the 2026–2040 climate projections. Their inputs, the ERA5-Land extension and the NEX-GDDP-CMIP6 files, stay in <code>riverine flood/long range/dataset</code> and are not charted in these data views.</p><div class="empty-steps"><span>Daily 180-day forecasts</span><span>Flood peaks</span><span>2026–2040 projections</span></div><button class="button" id="open-long-models">Open long-range models →</button> <button class="button secondary" id="back-marala">Explore short-range Marala data →</button></section>`;
    $('#open-long-models').onclick=()=>{location.hash='#models/long';};
    $('#back-marala').onclick=()=>{state.case='riverine';$('#station').value='marala';$('#horizon').value='short';renderCases();render();};
    return;
  }
  $('#empty-state').innerHTML=`<section class="empty-panel"><div class="empty-symbol" aria-hidden="true">${isJassar?'≋':'◫'}</div><div class="eyebrow">COLLECTION STATUS · NOT STARTED</div><h2>${esc(label)}${long?' · long range':''}</h2><p>No collected dataset is available for this model selection. Its workspace folders are ready; source coverage, integrity checks and plots will appear after data is collected and this portal snapshot is rebuilt.</p><div class="empty-steps"><span>1 · Collect source data</span><span>2 · Check and prepare</span><span>3 · Refresh the portal</span></div><p>Charts are shown only for datasets present in the project.</p><button class="button" id="back-marala">Explore collected Marala data →</button></section>`;
  $('#back-marala').onclick=()=>{state.case='riverine';$('#station').value='marala';$('#horizon').value='short';renderCases();render();};
}
function renderStationWorkspace(station){
  const view=state.view,folders=station.folders||[],files=station.files||[],series=station.series||[];
  const rowTable=`<div class="table-wrap"><table><thead><tr><th>Raw data folder</th><th>Files</th><th>Series</th><th>Coverage</th><th>Status</th></tr></thead><tbody>${folders.map(f=>`<tr><td><strong>${esc(f.name)}</strong><div class="cell-note"><code>${esc(station.path+'/'+f.id)}</code></div></td><td>${fmt(f.files)}</td><td>${fmt(f.series)}</td><td>${f.first_date?`${esc(f.first_date)} to ${esc(f.last_date)}`:'—'}</td><td>${f.files||f.series?pill('Data found','green'):pill('Waiting for data')}</td></tr>`).join('')}</tbody></table></div>`;
  const fileTable=`<div class="table-wrap"><table><thead><tr><th>File</th><th>Folder</th><th>Format</th><th>Size</th><th>Download</th></tr></thead><tbody>${files.map(f=>`<tr><td><strong>${esc(f.name)}</strong><div class="cell-note"><code>${esc(f.path)}</code></div></td><td>${esc(f.folder)}</td><td>${esc(f.format)}</td><td>${size(f.bytes)}</td><td>${f.download?`<a href="downloads/${esc(f.download)}" download>Download</a>`:'—'}</td></tr>`).join('')||`<tr><td colspan="5">No station files saved yet. The folders are ready for incoming data.</td></tr>`}</tbody></table></div>`;
  const title={overview:'Station overview',summary:'Station data summary',sources:'Station sources',quality:'Data quality',catchment:'Catchment and static data',library:'Station data library',rainfall:'Rainfall inputs'}[view]||'Station data';
  const subtitle=files.length?`${fmt(files.length)} files indexed across the registered raw folders.`:'No files found yet. The registered folder structure is ready; this page will populate after data is saved and the local snapshot refreshes.';
  let content='';
  if(view==='overview')content=`<div class="metrics">${metric('Raw folders',folders.length,'Registered station inputs','⌁')}${metric('Files found',files.length,'Across station raw folders','▤')}${metric('Date series',series.length,'Recognized date + numeric CSV columns','⌁')}${metric('Station',station.name,station.basin,'⌖')}</div><div class="two-column"><article class="card"><h2>Files by input folder</h2><div id="station-folder-chart" class="plot"></div></article><article class="card"><h2>Folder coverage</h2>${rowTable}</article></div>`;
  else if(view==='summary')content=`${rowTable}<article class="card"><h2>Static attributes</h2>${stationStaticTable(station)}</article><article class="card station-series-card"><div class="card-heading"><div><h2>Saved numeric series</h2><p>Daily values are read from CSV files with a date column. Values are displayed as saved.</p></div><label>Series<select id="station-series-select"></select></label></div><div id="station-series-chart" class="plot large"></div><div id="station-series-status" class="card-note">No date and numeric-value series found yet.</div></article>`;
  else if(view==='sources')content=`<article class="card"><h2>Files by station source folder</h2>${rowTable}</article><article class="card"><h2>Indexed source files</h2>${fileTable}</article>`;
  else if(view==='quality')content=`<article class="card"><h2>Coverage and file checks</h2><p>New station values remain unmodified. Missing dates are shown as missing; this portal does not interpolate observations.</p>${rowTable}</article><article class="card"><h2>Files awaiting review</h2>${files.length?fileTable:'<p class="card-note">No station files have arrived yet.</p>'}</article>`;
  else if(view==='catchment')content=`<article class="card"><h2>Catchment geometry</h2>${station.catchment?`<p>${esc(station.catchment.file)} · ${fmt(station.catchment.features||0)} features · ${esc((station.catchment.geometry_types||[]).join(', '))}</p>`:'<p>No catchment geometry saved for this station yet.</p>'}${station.catchment?.properties?`<div class="table-wrap"><table><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>${Object.entries(station.catchment.properties).map(([key,value])=>`<tr><td>${esc(key)}</td><td>${esc(value)}</td></tr>`).join('')}</tbody></table></div>`:''}</article><article class="card"><h2>Folder coverage and static attributes</h2>${rowTable}${stationStaticTable(station)}</article>`;
  else if(view==='rainfall')content=`<article class="card"><h2>Rainfall data</h2><p>Rainfall records are listed and plotted only when saved in the station’s raw rainfall folder.</p>${rowTable}<div id="station-rain-chart" class="plot"></div></article>`;
  else content=`<article class="card"><h2>Downloadable station files</h2>${fileTable}</article>`;
  $('#empty-state').innerHTML=`<section class="station-workspace"><div class="summary-intro"><div><div class="eyebrow">${esc(station.name.toUpperCase())} · ${esc(title.toUpperCase())}</div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div>${pill(station.status==='empty'?'Waiting for data':'Data available',station.status==='empty'?'':'green')}</div>${content}</section>`;
  if(view==='overview')plot('station-folder-chart',[{type:'bar',x:folders.map(f=>f.name),y:folders.map(f=>f.files),marker:{color:'#8caf7e'},hovertemplate:'%{x}<br>%{y} files<extra></extra>'}],{xaxis:{type:'category'},yaxis:{type:'linear',title:{text:'Files'}}});
  if(view==='summary'){
    const field=$('#station-series-select');field.replaceChildren(...series.map(s=>new Option(`${s.folder} · ${s.name}`,s.id)));
    const draw=()=>{const item=series.find(s=>s.id===field.value);if(!item){$('#station-series-status').textContent='No date and numeric-value series found yet. Add CSV files with a date column and numeric values to the station raw folders.';return plot('station-series-chart',[],{height:360});}$('#station-series-status').textContent=`${item.records} saved values from ${item.first_date} to ${item.last_date}; ${item.source_file}. Values are unmodified.`;return plot('station-series-chart',[{type:'scatter',mode:'lines',x:item.rows.map(r=>r.date),y:item.rows.map(r=>r.value),connectgaps:false,line:{color:colors.teal,width:1.7},hovertemplate:'%{x|%d %b %Y}<br>%{y:,.3f}<extra></extra>'}],{height:360,yaxis:{title:{text:item.unit}}});};field.onchange=()=>draw().catch(showRenderError);draw().catch(showRenderError);
  }
  if(view==='rainfall'){
    const rain=series.filter(s=>s.folder==='rainfall');plot('station-rain-chart',rain.length?rain.map(s=>({type:'scatter',mode:'lines',x:s.rows.map(r=>r.date),y:s.rows.map(r=>r.value),name:s.name,connectgaps:false})):[],{showlegend:rain.length>1});
  }
}
function stationStaticTable(station){
  const rows=station?.static_attributes||[];
  if(!rows.length)return '<p class="card-note">No static attribute values have been saved for this station yet.</p>';
  const values=new Map(rows.map(row=>[row.name,row.value]));
  const elevation=[
    ['elev_mean_m','Mean elevation','m',1],['elev_min_m','Minimum elevation','m',1],
    ['elev_p10_m','10th percentile','m',1],['elev_p50_m','Median elevation','m',1],
    ['elev_p90_m','90th percentile','m',1],['elev_max_m','Maximum elevation','m',1],
    ['frac_band1','Below 1,500 m','%',1,true],['frac_band2','1,500–3,000 m','%',1,true],
    ['frac_band3','3,000–4,500 m','%',1,true],['frac_band4','Above 4,500 m','%',1,true],
  ];
  const definitions=[
    {id:'elevation',title:'Elevation profile',source:'MERIT DEM · Google Earth Engine',items:elevation},
    {id:'terrain',title:'Catchment and terrain',source:'Catchment geometry · MERIT DEM · GLIMS',items:[
      ['area_km2','Catchment area','km²',1],['slope_mean_deg','Mean slope','°',1],['glacier_frac','Glacier area','%',1,true],
    ]},
    {id:'climate',title:'Climate context',source:'ECMWF ERA5-Land · 1980–2024',items:[
      ['precip_mean_mm','Mean annual precipitation','mm/year',1],['aridity','Aridity ratio','',3],
    ]},
    {id:'soil',title:'Soil composition',source:'OpenLandMap · 0–30 cm estimate',items:[
      ['sand_pct','Sand','%',1],['silt_pct','Silt','%',1],['clay_pct','Clay','%',1],
    ]},
    {id:'landcover',title:'Land cover',source:'ESA WorldCover v200 · 2021',items:[
      ['landcover_tree_cover','Tree cover','%',1,true],['landcover_shrubland','Shrubland','%',1,true],
      ['landcover_grassland','Grassland','%',1,true],['landcover_cropland','Cropland','%',1,true],
      ['landcover_built_up','Built-up','%',1,true],['landcover_bare_sparse','Bare / sparse vegetation','%',1,true],
      ['landcover_snow_ice','Snow and ice','%',1,true],['landcover_permanent_water','Permanent water','%',1,true],
      ['landcover_herbaceous_wetland','Herbaceous wetland','%',1,true],['landcover_mangroves','Mangroves','%',1,true],
      ['landcover_moss_lichen','Moss and lichen','%',1,true],
    ]},
  ];
  const used=new Set();
  const format=(value,decimals,multiplier=1)=>{
    const number=Number(value);
    return Number.isFinite(number)?new Intl.NumberFormat('en-US',{maximumFractionDigits:decimals}).format(number*multiplier):String(value);
  };
  const renderGroup=group=>{
    const items=group.items.filter(([key])=>values.has(key));
    if(!items.length)return '';
    items.forEach(([key])=>used.add(key));
    return `<section class="static-attribute-group" data-group="${esc(group.id)}"><header><div><span class="eyebrow">CATCHMENT ATTRIBUTE</span><h3>${esc(group.title)}</h3></div><span class="static-attribute-source">${esc(group.source)}</span></header><div class="static-attribute-grid">${items.map(([key,label,unit,decimals,percent])=>`<div class="static-attribute-tile"><span>${esc(label)}</span><strong>${esc(format(values.get(key),decimals,percent?100:1))}<small>${esc(unit)}</small></strong></div>`).join('')}</div></section>`;
  };
  const known=definitions.map(renderGroup).join('');
  const other=rows.filter(row=>!used.has(row.name));
  return `<div class="static-attribute-groups">${known}${other.length?`<section class="static-attribute-group"><header><div><span class="eyebrow">ADDITIONAL VALUES</span><h3>Other attributes</h3></div></header><div class="static-attribute-grid">${other.map(row=>`<div class="static-attribute-tile"><span>${esc(row.name)}</span><strong>${esc(row.value)}</strong></div>`).join('')}</div></section>`:''}</div>`;
}
function renderStationFolderSummary(station){
  const folders=station?.folders||[];
  $('#station-folder-summary-title').textContent=`${station?.name||'Station'} raw-folder coverage`;
  $('#station-folder-summary-table').innerHTML=`<table><thead><tr><th>Folder</th><th>Files</th><th>Series</th><th>Date coverage</th><th>Status</th></tr></thead><tbody>${folders.map(f=>`<tr><td><strong>${esc(f.name)}</strong><div class="cell-note"><code>${esc(station.path+'/'+f.id)}</code></div></td><td>${fmt(f.files)}</td><td>${fmt(f.series)}</td><td>${f.first_date?`${esc(f.first_date)} to ${esc(f.last_date)}`:'—'}</td><td>${f.files||f.series?pill('Data found','green'):pill('No files')}</td></tr>`).join('')}</tbody></table>`;
  const attrRows=(station?.static_attributes||[]).length;
  const catchment=station?.catchment;
  $('#station-static-summary-note').textContent=catchment?`Catchment file: ${catchment.file}; ${catchment.features??0} features · ${catchment.geometry_types.join(', ')||'geometry type unavailable'}. ${attrRows} static attribute values.`:`${attrRows} static attribute values found in the selected station workspace.`;
  $('#station-static-summary-table').innerHTML=stationStaticTable(station);
}
async function renderOverview(){
  const m=state.data.marala,base=m.quality.baseline;
  $('#overview-metrics').innerHTML=metric('Eligible daily inflow',fmt(base.eligible_daily_training_rows),`${fmt(base.rows)} source dates · <strong>7 withheld</strong>`,'≋')+metric('CHIRPS Final rain days',fmt(m.chirps_collection?.final_complete_days),`Catchment averages · <strong>complete saved span</strong>`,'⋮')+metric('Daily model-input series',(m.daily_inputs||[]).length,'Weather, evaporation and snow features found locally','⌁')+metric('Original files checked',fmt(state.data.integrity.counts.match),`${fmt(state.data.integrity.files.length)} checksum comparisons · <strong>local snapshot</strong>`,'✓');
  const inputCards=(m.daily_inputs||[]).map(s=>`<article class="input-series-tile"><strong>${esc(s.name)}</strong><span>${fmt(s.values)} / ${fmt(s.records)} dates with values</span><small>${esc(s.first_date)} to ${esc(s.last_date)} · ${esc(s.unit)}</small><a href="downloads/${esc(s.download)}" download>Download CSV</a></article>`).join('');
  $('#input-overview').innerHTML=inputCards||'<p class="card-note">No supported daily weather or snow input CSVs have been found yet.</p>';
  $('#input-refresh-state').textContent=`Snapshot ${new Date(state.data.built_utc).toLocaleTimeString('en-GB',{timeZone:'Asia/Karachi'})} PKT`;
  if(m.chirps_collection?.final_daily_rows)$('#research-note').innerHTML=`<span class="notice-icon">!</span><div><strong>CHIRPS Final is the plotted historical rainfall candidate.</strong><p>${fmt(m.chirps_collection.final_complete_days)} daily catchment values cover 1990 to ${esc(m.chirps_collection.final_end)}. The inconsistent saved NASA POWER values are omitted from precipitation charts and remain downloadable in the Data library for audit. CHIRPS still needs training-time and gauge checks.</p></div><a href="downloads/marala_chirps_v3_README.md" target="_blank">Open CHIRPS notes</a>`;
  else if(m.feature_coverage_audit?.rainfall_quality_blocked)$('#research-note').innerHTML='<span class="notice-icon">!</span><div><strong>Rainfall is not cleared for training.</strong><p>Dates match the WAPDA record, but saved long-range NASA responses disagree with independent short-period checks. Sample: 851.28 mm saved versus 35.47 mm from both a daily request and summed hourly values. Review the feature coverage audit before training.</p></div><a href="downloads/marala_feature_coverage_audit.json" target="_blank">Open audit ?</a>';
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
  $('#source-cards').innerHTML=sources.map(s=>{const bad=(s.counts.mismatch||0)+(s.counts.missing||0)+(s.counts.conflicting_claims||0);return `<article class="source-card"><div class="source-card-header"><span class="provider-mark">${esc(s.id==='nasa_power'?'NASA':s.name.slice(0,3).toUpperCase())}</span>${pill(s.url?(bad?'Needs review':'Hashes match'):'Local input',s.url?(bad?'red':'green'):'')}</div><div><h3>${esc(s.name)}</h3><div class="purpose">${esc(s.purpose)}</div></div><p class="source-note">${esc(s.note)}</p><div class="source-facts"><span>Checked files<strong>${fmt(s.files)}</strong></span><span>Source data size<strong>${size(s.bytes)}</strong></span><span>Matched hashes<strong>${fmt(s.counts.match||0)}</strong></span></div>${s.url?`<a class="source-link" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open provider source ↗</a>`:''}<details><summary>${fmt(s.links.length)} collected source links</summary><div class="more-links">${s.links.map(u=>`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`).join('')}</div></details></article>`;}).join('')||'<p class="card-note">No matching sources.</p>';
}
async function renderQuality(){
  const d=state.data,m=d.marala,ic=d.integrity.counts,b=m.quality.baseline;
  const fail=(ic.mismatch||0)+(ic.missing||0)+(ic.conflicting_claims||0);
  $('#quality-metrics').innerHTML=metric('Checksum exceptions',fmt(fail),`${fmt(ic.match)} files match saved receipts`,fail?'!':'✓')+metric('Withheld WAPDA dates',fmt(b.withheld_dates.length),'One zero and six source disagreements','!')+metric('Unconfirmed reading time',fmt(b.unknown_time_rows),'WAPDA dates · 1 companion-confirmed time','◷')+metric('Catchment checks',`${Object.values(m.catchment.checks).filter(Boolean).length} / ${Object.keys(m.catchment.checks).length}`,'Source and geometry checks · research boundary','◇');
  const layers=[['File integrity',`${fmt(ic.match)} local files match their saved checksum claims.`,true],['Legacy NASA rainfall preparation',`${fmt(m.rainfall_report.valid_daily_rows)} complete days; full catchment area. This older series is on hold.`,false],['Legacy NASA precipitation screen',`${fmt(m.rainfall_screening.count)} days exceed the advisory 100 mm/day screen; maximum ${fmt(m.rainfall_screening.maximum?.value)} mm/day. Review source plausibility. This is not an official invalid-data threshold.`,false],['Discharge consistency',`${b.exact_ffd_value_matches}/${b.ffd_comparisons} overlapping FFD values match WAPDA. Seven WAPDA days remain withheld.`,false],['Observation times',`${fmt(b.unknown_time_rows)} WAPDA dates lack an individually confirmed reading hour.`,false],['Boundary verification','Station location, area and geometry checks passed; no agency or field certification.',false]];
  if(m.chirps_collection?.final_daily_rows)layers.unshift(['CHIRPS preferred history',`${fmt(m.chirps_collection.final_complete_days)} of ${fmt(m.chirps_collection.final_daily_rows)} Final catchment days complete; ${fmt(m.chirps_collection.preliminary_daily_rows)} recent Preliminary days remain separate. Ten dates from the compact copy were checked against original CHC GeoTIFFs.`,true]);
  if((m.daily_inputs||[]).length)layers.unshift(['Daily model-input files',`${m.daily_inputs.length} weather/snow series are indexed from raw CSV files; their source values are shown without interpolation. New files without a saved checksum receipt appear as untracked until a collector records provenance.`,false]);
  if((d.integrity.untracked_files||[]).length)layers.unshift(['Raw files without checksum receipts',`${fmt(d.integrity.untracked_files.length)} raw files have no saved checksum claim. They remain visible in the Integrity ledger for review.`,false]);
  if(m.rainfall_source_comparison?.status){const p=m.rainfall_source_comparison.power_historical_profile;layers.unshift(['Rainfall source comparison',`Training hold: ${fmt(p.near_24_times)} historical NASA POWER cell-days differ by a factor of 24 across request ranges. Fresh POWER and original CHIRPS comparisons are saved separately. Read the investigation in the Data library.`,false]);}
  else if(m.feature_coverage_audit?.rainfall_quality_blocked)layers.unshift(['Rainfall source consistency','Training blocked: independent short-period daily and hourly checks disagree with saved long-range responses. Temporal coverage is complete, but rainfall values need to be revalidated.',false]);
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
  $('#catchment-metrics').innerHTML=metric('Upstream catchment',fmt(Math.round(c.area_km2_geodesic)),'km² · WGS84 geodesic area','◇')+metric('POWER audit grid',r.grid_cells,'NASA cells shown on this map','▦')+metric('CHIRPS grid',m.chirps_collection?.catchment_cells||0,'Cells in plotted rainfall series','✓')+metric('Station location','32.67° N','74.46° E · JICA / PMD inventory','⌖');
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
  $('#library-categories').innerHTML=['all','discharge','daily model inputs','rainfall','catchment','metadata'].map(c=>`<button data-category="${c}" class="${c===state.fileCategory?'active':''}">${nice(c)}</button>`).join('');$$('[data-category]').forEach(b=>b.onclick=()=>{state.fileCategory=b.dataset.category;renderLibrary();});
  const term=$('#file-search').value.toLowerCase();const files=state.data.downloads.filter(f=>(state.fileCategory==='all'||f.category===state.fileCategory)&&(f.name+' '+f.path).toLowerCase().includes(term));
  $('#file-rows').innerHTML=files.map(f=>`<tr><td><strong>${esc(f.name)}</strong><div class="cell-note"><code>${esc(f.path)}</code></div><details><summary>SHA-256</summary><code>${esc(f.sha256)}</code></details></td><td>${pill(nice(f.category))}</td><td>${size(f.bytes)}</td><td>${f.url?`<a href="${esc(f.url)}" download>Download ↓</a><a href="${esc(f.url)}" target="_blank" rel="noopener">Open ↗</a>`:'<span class="cell-note">Large source-cell table available in the local project</span>'}</td></tr>`).join('')||'<tr><td colspan="4">No matching files.</td></tr>';
}
function applyYear(){const y=$('#year').value;if(y==='all'){let first=null,last=null;const consider=row=>{if(!first||row.date<first)first=row.date;if(!last||row.date>last)last=row.date;};for(const row of state.data.marala.inflow)consider(row);for(const row of state.data.marala.precipitation)consider(row);for(const series of state.data.marala.daily_inputs||[])for(const row of series.rows)consider(row);$('#from-date').value=first||'';$('#to-date').value=last||'';}else if(y!=='custom'){$('#from-date').value=`${y}-01-01`;$('#to-date').value=`${y}-12-31`;if(state.data.marala.events.some(e=>e.id===y))$('#event').value=y;}render().catch(showRenderError);}
function showRenderError(error){console.error(error);toast(`Could not render this view: ${error.message}`);}
window.addEventListener('hashchange',()=>render().catch(showRenderError));
window.addEventListener('resize',()=>$$('.js-plotly-plot').filter(el=>el.offsetParent).forEach(el=>Plotly.Plots.resize(el)));
$('#reload').onclick=async()=>{await loadData();toast('Reloaded the latest saved data snapshot.');};
$('#station').onchange=()=>render().catch(showRenderError);$('#horizon').onchange=()=>{if(['models','analyzer'].includes(state.view))history.replaceState(null,'',`#${state.view}/${$('#horizon').value}`);render().catch(showRenderError);};$('#year').onchange=applyYear;
for(const id of ['#from-date','#to-date'])$(id).onchange=()=>{if($('#from-date').value>$('#to-date').value){toast('Choose a start date before the end date.');return;}$('#year').value='custom';render().catch(showRenderError);};
$('#reset-dates').onclick=()=>{$('#year').value='all';applyYear();};$('#show-ffd').onchange=()=>renderOverview().catch(showRenderError);$('#event').onchange=()=>renderEvent().catch(showRenderError);
$('#source-search').oninput=renderSources;$('#integrity-search').oninput=()=>{state.ledgerPage=0;renderLedger();};$('#file-search').oninput=renderLibrary;$('#show-grid').onchange=()=>renderCatchment().catch(showRenderError);
$('#menu-toggle').onclick=()=>{const open=$('#sidebar').classList.toggle('open');$('#menu-toggle').setAttribute('aria-expanded',String(open));};
$$('[data-view]').forEach(a=>a.addEventListener('click',()=>{$('#sidebar').classList.remove('open');$('#menu-toggle').setAttribute('aria-expanded','false');if(location.hash===a.getAttribute('href'))render().catch(showRenderError);}));
loadData();
setInterval(async()=>{
  if(document.hidden||!state.data)return;
  try{
    const response=await fetch(`data/build_report.json?check=${Date.now()}`,{cache:'no-store'});
    if(!response.ok)return;
    const manifest=await response.json();
    if(manifest.snapshot_built_utc&&manifest.snapshot_built_utc!==state.data.built_utc){await loadData({automatic:true});return;}
    const modelsBuilt=manifest.models?.built_utc,loadedModels=window.FloodModels?.builtUtc();
    if(modelsBuilt&&loadedModels&&modelsBuilt!==loadedModels&&modelsBuilt!==state.modelsNotified){
      state.modelsNotified=modelsBuilt;
      await window.FloodModels.refresh();
      if(['models','analyzer'].includes(state.view))await render();
      const changes=manifest.models.changes||[];
      toast(changes.length?`Model results updated: ${changes.slice(0,3).map(change=>`${change.name} v${change.version}`).join(', ')}${changes.length>3?` and ${changes.length-3} more`:''}.`:'Model results updated.');
    }
  }catch(error){console.debug('Automatic snapshot check skipped:',error.message);}
},12000);
