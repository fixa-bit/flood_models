'use strict';

// Keep each catchment rainfall series separate in the data while allowing a
// shared-date comparison, individual plots, and an availability view.
window.FloodRainfall = (() => {
  const DAY = 86400000;
  const colors = {
    gee_era5land:'#f4c76b',gee_chirps:'#f598bd',gee_persiann:'#b0b9ff',gee_imerg:'#f28f6d',
    chirps_final: '#75d0ac', chirps_preliminary: '#c7a7e7',
    nasa_fresh: '#8db9df',
    chirps_original_samples: '#82d4d0',
  };
  const state = {bound: false, year: '2024', source: 'all', availabilityYear: 'all'};
  const byId = id => document.getElementById(id);
  const fmt = value => Number(value || 0).toLocaleString('en-US');
  const clean = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const valid = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const iso = milliseconds => new Date(milliseconds).toISOString().slice(0,10);
  const pretty = date => new Date(date + 'T00:00:00Z').toLocaleDateString('en-GB',{timeZone:'UTC',day:'numeric',month:'short',year:'numeric'});

  function selectors(sources) {
    const dates = sources.flatMap(source => source.rows.map(row => row.date)).sort();
    if (!dates.length) return;
    state.first = dates[0];
    state.last = dates.at(-1);
    const firstYear = Number(state.first.slice(0,4));
    const lastYear = Number(state.last.slice(0,4));
    const years = Array.from({length:lastYear-firstYear+1}, (_,index) => String(firstYear+index));
    for (const [id, selected] of [['rainfall-year',state.year],['rainfall-availability-year',state.availabilityYear]]) {
      const field = byId(id);
      field.replaceChildren(new Option('All collected years','all'), ...years.map(year => new Option(year,year)));
      field.value = selected === 'all' || years.includes(selected) ? selected : 'all';
    }
    const filter = byId('rainfall-source');
    filter.replaceChildren(new Option('All sources','all'),...sources.map(source => new Option(source.name,source.id)));
    filter.value = sources.some(source=>source.id===state.source) ? state.source : 'all';
  }

  function metrics(sources) {
    const get = id => sources.find(source=>source.id===id);
    const final = get('chirps_final');
    const preliminary = get('chirps_preliminary');
    const other = sources.filter(source=>!source.id.startsWith('chirps_')).reduce((sum,source)=>sum+source.values,0);
    const data = [
      ['CHIRPS Final',fmt(final?.values),'Daily catchment values · 1990 to Sep 2026'],
      ['CHIRPS Preliminary',fmt(preliminary?.values),'Recent days · kept separate'],
      ['Other source values',fmt(other),'Separate comparison datasets'],
      ['Rainfall datasets',fmt(sources.length),'Each shown in its own panel'],
    ];
    byId('rainfall-metrics').innerHTML=data.map(([label,value,note])=>
      `<article class="metric"><div class="metric-label">${clean(label)}</div><div class="metric-value">${clean(value)}</div><div class="metric-foot">${clean(note)}</div></article>`).join('');
  }

  async function comparison(sources) {
    const year=state.year;
    const range=year==='all' ? [state.first,state.last] : [`${year}-01-01`,`${Number(year)+1}-01-01`];
    const traces=sources.map(source=>{
      const rows=source.rows.filter(row=>(year==='all'||row.date.startsWith(year))&&valid(row.value));
      const sample=source.id.endsWith('samples');
      return {type:'scattergl',mode:sample?'markers':'lines',name:source.name,
        x:rows.map(row=>row.date),y:rows.map(row=>row.value),yaxis:'y',
        line:{color:colors[source.id],width:1.8},
        marker:{color:colors[source.id],size:sample?8:4},
        customdata:rows.map(row=>row.flag||source.status),
        hovertemplate:'%{y:.2f} mm<br>%{customdata}<extra>%{fullData.name}</extra>'};
    });
    const graph=byId('rainfall-comparison-plot');
    const layout={height:420,autosize:true,margin:{l:64,r:25,t:35,b:80},
      paper_bgcolor:'transparent',plot_bgcolor:'transparent',hovermode:'x unified',
      font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},
      hoverlabel:{bgcolor:'#111c17',bordercolor:'#697a5d',font:{size:11,color:'#eef0e5'}},
      legend:{orientation:'h',x:0,y:-.22,font:{size:10},itemclick:'toggle',itemdoubleclick:'toggleothers'},
      xaxis:{type:'date',range,showgrid:true,gridcolor:'#27372d',tickformat:year==='all'?'%Y':'%d %b',
        showspikes:true,spikemode:'across',spikesnap:'cursor',spikecolor:'#d5ddce',spikethickness:1},
      yaxis:{title:{text:'Rainfall (mm/day)',font:{size:10}},rangemode:'tozero',showgrid:true,gridcolor:'#27372d'}};
    await Plotly.react(graph,traces,layout,{responsive:true,displaylogo:false,scrollZoom:false,
      modeBarButtons:[['zoom2d','pan2d','resetScale2d','toImage']]});
  }

  async function panels(sources) {
    const chosen = state.source==='all' ? sources : sources.filter(source=>source.id===state.source);
    const holder=byId('rainfall-panels');
    holder.replaceChildren();
    const year=state.year;
    const range=year==='all' ? [state.first,state.last] : [`${year}-01-01`,`${Number(year)+1}-01-01`];
    for (const source of chosen) {
      const rows=source.rows.filter(row=>year==='all'||row.date.startsWith(year));
      const values=rows.filter(row=>valid(row.value));
      const missing=rows.filter(row=>!valid(row.value));
      const article=document.createElement('article');article.className='rainfall-panel';
      const title=document.createElement('div');title.className='rainfall-panel-heading';
      const label=document.createElement('div');
      const heading=document.createElement('h3');heading.textContent=source.name;
      const note=document.createElement('p');note.textContent=`${source.method} ${source.status}.`;
      label.append(heading,note);
      const facts=document.createElement('div');facts.className='rainfall-panel-facts';
      const count=document.createElement('span');count.textContent=`${fmt(values.length)} readings ${year==='all'?'in the collection':'in '+year}`;
      const link=document.createElement('a');link.href=`downloads/${encodeURIComponent(source.download)}`;link.download=source.download;link.textContent='Download CSV';
      facts.append(count,link);title.append(label,facts);article.append(title);
      if (values.length) {
        const graph=document.createElement('div');graph.className='rainfall-source-plot';
        graph.setAttribute('aria-label',`${source.name} catchment rainfall values for ${year==='all'?'all collected years':year}`);
        article.append(graph);holder.append(article);
        const isSample=source.id.endsWith('samples');
        const useBars=year!=='all'&&!isSample;
        const trace={type:useBars?'bar':'scattergl',mode:useBars?undefined:(isSample?'markers':'lines'),
          x:values.map(row=>row.date),y:values.map(row=>row.value),
          marker:{color:colors[source.id],size:isSample?8:4,opacity:.88},
          line:{color:colors[source.id],width:1.4},
          customdata:values.map(row=>[row.flag||source.status,row.representation||'',row.coverage]),
          hovertemplate:'<b>%{x|%d %b %Y}</b><br>%{y:.3f} mm over catchment<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>'};
        const layout={height:205,autosize:true,margin:{l:62,r:25,t:12,b:44},
          paper_bgcolor:'transparent',plot_bgcolor:'transparent',showlegend:false,hovermode:'closest',
          font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},
          hoverlabel:{bgcolor:'#111c17',bordercolor:'#697a5d',font:{size:11,color:'#eef0e5'}},
          xaxis:{type:'date',range,showgrid:true,gridcolor:'#27372d',tickformat:year==='all'?'%Y':'%d %b',
            zeroline:false,showspikes:true,spikemode:'across',spikecolor:'#d5ddce'},
          yaxis:{title:{text:'Rain (mm)',font:{size:10}},rangemode:'tozero',showgrid:true,gridcolor:'#27372d',zeroline:false}};
        await Plotly.newPlot(graph,[trace],layout,{responsive:true,displaylogo:false,scrollZoom:false,
          modeBarButtons:[['zoom2d','pan2d','resetScale2d','toImage']]});
      } else {
        const empty=document.createElement('p');empty.className='rainfall-empty';
        empty.textContent=`No valid ${source.name} catchment value is saved for ${year==='all'?'this collection':year}.`;
        article.append(empty);holder.append(article);
      }
      if (missing.length) {
        const issues=document.createElement('p');issues.className='rainfall-issue';
        issues.textContent=missing.map(row=>{
          return `${row.date}: ${row.flag||'value missing'}`;
        }).join(' · ');
        article.append(issues);
      }
    }
  }

  async function availability(sources) {
    const year=state.availabilityYear;
    const first=year==='all'?state.first:`${year}-01-01`;
    const last=year==='all'?state.last:`${year}-12-31`;
    const start=Date.parse(first+'T00:00:00Z'),end=Date.parse(last+'T00:00:00Z');
    const dates=Array.from({length:Math.round((end-start)/DAY)+1},(_,i)=>iso(start+i*DAY));
    const sets=sources.map(source=>new Map(source.rows.map(row=>[row.date,row])));
    const width=Math.min(16000,Math.max(1200,dates.length*4));
    const viewport=byId('rainfall-availability-viewport');
    const graph=byId('rainfall-availability-chart');
    graph.style.width=width+'px';
    const legend=byId('rainfall-availability-legend');
    legend.replaceChildren(...sources.map(source=>{
      const span=document.createElement('span'),dot=document.createElement('i');
      dot.style.background=colors[source.id];span.append(dot,document.createTextNode(source.name));return span;
    }));
    const colorStops=[];
    ['#26312c',...sources.map(source=>colors[source.id])].forEach((color,index)=>{
      colorStops.push([Math.max(0,(index-.5)/sources.length),color],
        [Math.min(1,(index+.5)/sources.length),color]);
    });
    const traces=[{type:'heatmap',x:dates,y:sources.map(source=>source.name),
      z:sources.map((source,index)=>dates.map(day=>valid(sets[index].get(day)?.value)?index+1:0)),
      zmin:0,zmax:sources.length,colorscale:colorStops,
      customdata:sources.map((source,index)=>dates.map(day=>{
        const row=sets[index].get(day);
        const status=row ? (valid(row.value)?'Valid saved value':`Saved record, value withheld: ${row.flag||'missing'}`) : 'No saved record';
        return `${source.name}<br>${status}<br>${source.status}`;
      })),
      showscale:false,xgap:year==='all'?0:1,ygap:6,
      hovertemplate:'<b>%{x|%d %b %Y}</b><br>%{customdata}<extra></extra>'}];
    if (graph._fullLayout) Plotly.purge(graph);
    await Plotly.newPlot(graph,traces,{width,autosize:false,height:375,margin:{l:210,r:20,t:20,b:55},
      paper_bgcolor:'transparent',plot_bgcolor:'transparent',showlegend:false,
      font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},
      hoverlabel:{bgcolor:'#111c17',bordercolor:'#697a5d',font:{size:11,color:'#eef0e5'}},
      xaxis:{type:'date',range:[first,last],tickformat:year==='all'?'%Y':'%d %b',showgrid:false,fixedrange:true,
        title:{text:`Calendar date · ${year==='all'?'all collected years':year}`,font:{size:11}}},
      yaxis:{type:'category',categoryorder:'array',categoryarray:sources.map(source=>source.name),autorange:'reversed',
        showgrid:false,fixedrange:true},uirevision:`rainfall-availability-${year}`},
      {responsive:true,displaylogo:false,scrollZoom:false,modeBarButtons:[['toImage']]});
    viewport.scrollLeft=0;
  }

  function bind() {
    if (state.bound) return;
    state.bound=true;
    byId('rainfall-year').onchange=event=>{state.year=event.target.value;comparison(state.sources).then(()=>panels(state.sources)).catch(console.error);};
    byId('rainfall-source').onchange=event=>{state.source=event.target.value;panels(state.sources).catch(console.error);};
    byId('rainfall-availability-year').onchange=event=>{state.availabilityYear=event.target.value;availability(state.sources).catch(console.error);};
  }

  async function render(marala) {
    const sources=marala.rainfall_sources||[];
    state.sources=sources;
    selectors(sources);metrics(sources);bind();
    await comparison(sources);
    await panels(sources);
    await availability(sources);
  }

  return {render};
})();
