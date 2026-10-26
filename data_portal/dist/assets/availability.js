'use strict';

// The all-history availability calendar has its own viewport and scroll state. Colored
// cells mean a source reading exists, including withheld readings and valid zeroes.
window.FloodAvailability = (() => {
  const DAY=86400000;
  const definitions=[
    {name:'Inflow discharge',short:'Inflow discharge',color:'#75d0ac'},
    {name:'Outflow discharge',short:'Outflow discharge',color:'#8db9df'},
    {name:'Catchment precipitation',short:'Catchment precipitation',color:'#efb35e'},
    {name:'Daily mean inflow',short:'Daily mean inflow',color:'#c6abd8'},
    {name:'Daily mean outflow',short:'Daily mean outflow',color:'#f2a0bf'},
    {name:'Selected flood peak',short:'Selected flood peak',color:'#73d2df'},
  ];
  const state={bound:false,dates:[],days:0,year:'all'};
  const select=id=>document.getElementById(id);
  const valid=value=>value!==null&&value!==undefined&&Number.isFinite(Number(value));
  const iso=milliseconds=>new Date(milliseconds).toISOString().slice(0,10);
  const dateFormatter=new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',day:'numeric',month:'long',year:'numeric'});
  const pretty=day=>dateFormatter.format(new Date(day+'T00:00:00Z'));

  function setSpan(data) {
    state.data=data;
    const recorded=['inflow','ffd','precipitation','irsa','peaks'].flatMap(key=>data[key].map(row=>row.date)).sort();
    const firstYear=Number(recorded[0].slice(0,4)),lastYear=Number(recorded.at(-1).slice(0,4));
    if(state.year!=='all'&&(Number(state.year)<firstYear||Number(state.year)>lastYear)) state.year='all';
    state.first=state.year==='all'?recorded[0]:`${state.year}-01-01`;
    state.last=state.year==='all'?recorded.at(-1):`${state.year}-12-31`;
    state.start=Date.parse(state.first);state.end=Date.parse(state.last)+DAY;
    state.days=Math.round((state.end-state.start)/DAY);
    state.dates=Array.from({length:state.days},(_,index)=>iso(state.start+index*DAY));
    state.dateLabels=state.dates.map(pretty);
    select('availability-span').textContent=`${pretty(state.first)} to ${pretty(state.last)} — ${state.year==='all'?'all saved years':'selected calendar year'}`;
    select('availability-first-date').textContent=pretty(state.first);
    select('availability-last-date').textContent=pretty(state.last);
    select('availability-viewport').setAttribute('aria-label',`Independent data availability chart: ${state.year==='all'?'all collected years':state.year}`);
    select('availability-chart').setAttribute('aria-label',`Date-by-variable availability matrix for ${state.year==='all'?'all collected years':state.year}, with no measurement values`);
    const field=select('availability-year');
    field.replaceChildren(new Option('All collected years','all'),...Array.from({length:lastYear-firstYear+1},(_,index)=>{
      const year=firstYear+index;return new Option(String(year),String(year));
    }));
    field.value=state.year;
  }

  function byDate(rows) {
    const groups=new Map();
    for(const row of rows) {
      if(!groups.has(row.date)) groups.set(row.date,[]);
      groups.get(row.date).push(row);
    }
    return groups;
  }

  function calendar(data) {
    const wapda=byDate(data.inflow),ffd=byDate(data.ffd),rain=byDate(data.precipitation);
    const irsa=byDate(data.irsa),peaks=byDate(data.peaks);
    const cells=definitions.map((definition,index)=>state.dates.map((day,dayIndex)=>{
      const w=wapda.get(day)?.[0],f=ffd.get(day)||[],r=rain.get(day)?.[0];
      const i=irsa.get(day)||[],p=peaks.get(day)||[];
      const sources=[],times=[],issues=[];
      let present=false;
      if(index===0||index===1) {
        if(index===0&&w&&valid(w.source_value)) {
          present=true;sources.push('WAPDA');
          times.push(w.time?`WAPDA: ${w.time} Pakistan time`:'WAPDA: observation hour not confirmed');
          if(!w.eligible) issues.push('WAPDA reading excluded from training pending review.');
        }
        const rows=f.filter(row=>valid(row[index===0?'inflow':'outflow']));
        if(rows.length) {
          present=true;sources.push('FFD');times.push('FFD: 06:00 Pakistan time');
          if(rows.some(row=>row.flag)) issues.push('An FFD bulletin date disagrees with its archive date.');
          if(rows.length>1) issues.push('Multiple FFD records use this printed date.');
        }
      } else if(index===2&&r&&valid(r.value)) {
        present=true;sources.push('NASA POWER');
        times.push('24-hour period: 05:00 Pakistan time to next 05:00 (00:00 to next 00:00 UTC)');
        if(data.feature_coverage_audit?.rainfall_quality_blocked) issues.push('Precipitation dataset on hold for training: source downloads disagree.');
      } else if(index===3||index===4) {
        present=i.some(row=>valid(row[index===3?'inflow':'outflow']));
        if(present) {sources.push('IRSA');times.push('Daily average; exact start and end hours not stated');}
      } else if(index===5) {
        present=p.some(row=>valid(row.value));
        if(present) {sources.push('PMD journal');times.push('Selected event maximum; reading time not stated');}
      }
      return {date:day,present,review:present&&issues.length>0,
        detail:[state.dateLabels[dayIndex],definition.name,present?'Reading saved':'No saved reading',
          sources.length?sources.join(' + '):'None saved in this project',
          times.length?times.join('<br>'):'No saved reading time for this date',
          issues.length?issues.join('<br>'):(present?'Presence only; this does not certify quality.':'Missing in the collected dataset; no value filled in.')]};
    }));
    return cells;
  }

  // Cap the wide SVG/image below browser canvas dimension limits, including
  // the 2x PNG export. The complete daily history remains in the same plot.
  function width() {return Math.min(16000,Math.max(3036,state.days*4+198,select('availability-viewport').clientWidth*2));}
  function controls() {
    const viewport=select('availability-viewport'),slider=select('availability-scroll'),graph=select('availability-chart');
    const maximum=Math.max(0,viewport.scrollWidth-viewport.clientWidth);
    slider.max=maximum;slider.value=Math.round(viewport.scrollLeft);slider.disabled=maximum===0;
    if(!graph._fullLayout?._size) return;
    const layout=graph._fullLayout,plotWidth=layout.xaxis._length;
    const first=Math.max(0,Math.min(state.days-1,Math.floor(viewport.scrollLeft/plotWidth*state.days)));
    const last=Math.max(first,Math.min(state.days-1,Math.ceil((viewport.scrollLeft+viewport.clientWidth-layout.margin.l)/plotWidth*state.days)-1));
    const text=`Visible dates: ${pretty(state.dates[first])} to ${pretty(state.dates[last])}. Independent of the value graphs.`;
    select('availability-visible-dates').textContent=text;slider.setAttribute('aria-valuetext',text);
  }

  function labels() {
    const graph=select('availability-chart'),holder=select('availability-labels'),layout=graph._fullLayout;
    if(!layout?._size) return;
    holder.style.width=layout.margin.l+'px';
    holder.replaceChildren(...definitions.map((definition,index)=>{
      const label=document.createElement('div');label.className='availability-variable';
      label.style.top=(layout.yaxis._offset+layout.yaxis.d2p(definition.name)-19)+'px';
      label.style.setProperty('--variable-color',definition.color);
      const name=document.createElement('strong');name.textContent=definition.short;
      const count=document.createElement('span');
      count.textContent=state.cells[index].filter(cell=>cell.present).length.toLocaleString('en-US')+' dates saved';
      label.append(name,count);return label;
    }));
  }

  async function resize() {
    const graph=select('availability-chart');
    if(state.rendering||!graph._fullLayout?._size||select('summary-view').hidden||select('populated').hidden) return;
    const next=width();graph.style.width=next+'px';
    await Plotly.relayout(graph,{width:next,autosize:false,'margin.l':window.innerWidth<700?146:176});
    labels();controls();
  }

  function bind() {
    if(state.bound) return;
    state.bound=true;
    const viewport=select('availability-viewport');
    viewport.addEventListener('scroll',controls);
    select('availability-scroll').oninput=event=>{viewport.scrollLeft=Number(event.target.value);controls();};
    select('availability-year').onchange=event=>{
      state.year=event.target.value;
      viewport.scrollLeft=0;
      render(state.data).catch(console.error);
    };
    window.addEventListener('resize',()=>{
      clearTimeout(state.resizeTimer);state.resizeTimer=setTimeout(()=>resize().catch(console.error),80);
    });
  }

  async function render(data) {
    setSpan(data);
    select('availability-year').disabled=true;
    state.cells=calendar(data);
    select('availability-legend').replaceChildren(...definitions.map(definition=>{
      const label=document.createElement('span'),dot=document.createElement('i');
      dot.style.background=definition.color;label.append(dot,definition.name);return label;
    }));
    const details=state.cells.map(row=>row.map(cell=>cell.detail));
    const hover='<b>%{customdata[0]}</b><br>%{customdata[1]}<br><b>%{customdata[2]}</b><br>Source: %{customdata[3]}<br>%{customdata[4]}<br>%{customdata[5]}<extra></extra>';
    const review={x:[],y:[],customdata:[]};
    state.cells.forEach((row,index)=>row.forEach(cell=>{
      if(cell.review){review.x.push(cell.date);review.y.push(definitions[index].name);review.customdata.push(cell.detail);}
    }));
    const traces=[{
      type:'heatmap',x:state.dates,y:definitions.map(row=>row.name),
      z:state.cells.map((row,index)=>row.map(cell=>cell.present?index+1:0)),
      zmin:0,zmax:6,colorscale:[[0,'#26312c'],...definitions.map((row,index)=>[(index+1)/6,row.color])],
      customdata:details,hovertemplate:hover,showscale:false,xgap:state.year==='all'?0:1,ygap:7,hoverongaps:false,
    },{
      type:'scatter',mode:'markers',...review,marker:{color:'#fff6d4',size:3},hovertemplate:hover,showlegend:false,
    }];
    const next=width();select('availability-chart').style.width=next+'px';
    const layout={width:next,autosize:false,height:420,paper_bgcolor:'transparent',plot_bgcolor:'transparent',
      margin:{l:window.innerWidth<700?146:176,r:22,t:42,b:58},showlegend:false,dragmode:false,hovermode:'closest',
      font:{family:'Inter, Segoe UI, sans-serif',size:10,color:'#b6c6ae'},
      hoverlabel:{bgcolor:'#111c17',bordercolor:'#697a5d',font:{size:11,color:'#eef0e5'}},
      xaxis:{type:'date',range:[state.first,new Date(state.end-1).toISOString()],fixedrange:true,
        dtick:state.year==='all'?'M3':7*DAY,tick0:state.first.slice(0,4)+'-01-01',tickformat:state.year==='all'?'%b<br>%Y':'%d %b',showgrid:false,
        title:{text:`Calendar date · ${state.year==='all'?'all collected years':state.year}`,font:{size:11}},showspikes:true,spikemode:'across',spikesnap:'data',spikecolor:'#d5ddce',spikethickness:1},
      yaxis:{type:'category',categoryorder:'array',categoryarray:definitions.map(row=>row.name),autorange:'reversed',
        showticklabels:false,showgrid:false,zeroline:false,fixedrange:true},
      uirevision:`marala-availability-${state.year}`,
    };
    state.rendering=true;
    try {await Plotly.react('availability-chart',traces,layout,{responsive:true,displaylogo:false,scrollZoom:false,
      modeBarButtons:[['toImage']],toImageButtonOptions:{format:'png',filename:`marala_data_availability_${state.year}`,scale:2}});}
    finally {state.rendering=false;select('availability-year').disabled=false;}
    bind();labels();controls();
  }

  return {render};
})();
