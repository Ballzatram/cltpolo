/* Investor page controller: atomic snapshots, source health, bounded in-page refresh. */
(function () {
  'use strict';
  const R=window.PoloResearch, D=window.PoloResearchData, $=id=>document.getElementById(id);
  const RAW='https://raw.githubusercontent.com/Ballzatram/cltpolo/main/';
  const RUNS='https://api.github.com/repos/Ballzatram/cltpolo/actions/workflows/267977853/runs?branch=main&per_page=5';
  const agent=$('runPropertyAgent');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const slug=value=>String(value??'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
  const name=row=>R.field(row,['Property Name','Address / Property','ID'])||'Unnamed research lead';
  const id=row=>slug(R.field(row,['ID','Listing External ID','Dashboard Slug','Property URL','Source URL'])||name(row));
  const date=value=>D.timestamp(value)===null?'Not established':new Intl.DateTimeFormat('en-US',{dateStyle:'medium',timeZone:'America/New_York'}).format(new Date(value));
  const money=value=>{const n=R.number(value);return n>0?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n):'Not established';};
  function read(key,session=false){try{return JSON.parse((session?sessionStorage:localStorage).getItem(key)||'null');}catch{return null;}}
  function write(key,value,session=false){try{(session?sessionStorage:localStorage).setItem(key,JSON.stringify(value));}catch{/* Page-local state remains usable. */}}
  let saved=read('cltPoloSavedResearch');if(!Array.isArray(saved))saved=[];saved=new Set(saved.filter(v=>typeof v==='string'));
  let userVotes=read('cltPoloPropertyVotes');if(!userVotes||typeof userVotes!=='object'||Array.isArray(userVotes))userVotes={};
  let snapshot,entries=[],map,markers,sequence=0,tallies={},votesAvailable=false,watch=null,watchTimer=null;
  const pendingVotes=new Set();
  function notice(message,type='info'){$('propertyAgentStatus').hidden=false;$('propertyAgentStatus').textContent=message;$('propertyAgentStatus').dataset.status=type;}
  async function request(url,options={}){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{
      const response=await fetch(url,{cache:'no-store',credentials:'omit',...options,signal:controller.signal});
      if(!response.ok){const error=new Error(`HTTP ${response.status}`);error.status=response.status;throw error;}
      return await(options.text?response.text():response.json());
    }finally{clearTimeout(timer);}
  }
  function route(row){const loc=R.coordinates(row),destination=loc?`${loc.lat},${loc.lng}`:[R.field(row,['Address / Property','Property Name']),row.City,row.State].filter(Boolean).join(', ');return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent('Uptown Charlotte, NC')}&destination=${encodeURIComponent(destination)}&travelmode=driving`;}
  function filtered(){
    const query=$('investorSearch').value.trim().toLowerCase(),view=$('researchView').value,terrain=$('terrainFilter').value;
    return entries.filter(({row,fit})=>(view==='all'||view==='active'&&fit.status!=='outside'||view==='saved'&&saved.has(id(row))||view===fit.status)
      &&(!terrain||(terrain==='verified')===fit.terrainVerified)&&(!query||Object.values(row).join(' ').toLowerCase().includes(query))).sort((a,b)=>R.compare(a,b,$('sortFilter').value));
  }
  function sourceHealth(origin){
    const health=snapshot.health||{};
    $('healthTitle').textContent=D.healthLabel(health);
    $('healthMessage').textContent=health.message||'No source-health report is available. The saved records have not been reverified by loading this page.';
    $('lastAttempt').textContent=date(health.attemptedAt);
    $('lastReview').textContent=date(snapshot.latestListingReviewAt);
    $('dataOrigin').textContent=origin;
    const sources=Array.isArray(health.sources)?health.sources:[];
    const paused=Array.isArray(health.pausedPortals)?health.pausedPortals:snapshot.brief.pausedPortals||[];
    $('sourceHealth').innerHTML=sources.map(source=>`<div class="source-row"><strong>${escape(source.name)} · ${escape(source.status)}${source.http?` · HTTP ${escape(source.http)}`:''}</strong><p>${escape(source.note||'')}</p></div>`).join('')
      +paused.map(source=>`<div class="source-row"><strong>${escape(source.name)} · paused</strong><p>${escape(source.reason)}</p></div>`).join('')
      +`<p>${escape(health.coverage||'Configured broker pages do not cover the full Charlotte-to-Columbia land market.')}</p>`;
    $('browseSources').innerHTML=(snapshot.brief.sources||[]).slice(0,3).map(source=>{const url=R.safeUrl(source.url);return url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(source.name)}</a>`:'';}).join('');
  }
  function card({row,fit,fresh},index){
    const key=id(row),url=R.safeUrl(R.field(row,['Property URL','Source URL'])),cardId=`property-${key}-${index}`;
    const checks=fit.checks.map(check=>`<div class="check"><strong>${escape(check.label)} · ${check.state==='pass'?'Documented':check.state==='fail'?'Conflict':'Unverified'}</strong><p>${escape(check.note)}</p>${check.valid?`<a href="${escape(check.url)}" target="_blank" rel="noopener noreferrer">Evidence · ${escape(check.date)}</a>`:''}</div>`).join('');
    const tally=tallies[key]||{};
    return `<article class="property-card" id="${cardId}"><div class="card-head"><div class="badges"><span class="badge" data-state="${fit.status}">${escape(fit.label)}</span>${fresh.state!=='recent'?`<span class="badge" data-state="${fresh.state}">${fresh.state==='stale'?'Old source review':'Review date unknown'}</span>`:''}</div><h3>${escape(name(row))}</h3><p>${escape([row.City,row.County,row.State].filter(Boolean).join(' · '))}</p></div>
      <div class="card-body"><dl class="card-facts"><div><dt>Parcel acreage</dt><dd>${fit.acres??'Not established'}</dd></div><div><dt>Recorded asking price</dt><dd>${escape(money(row['List Price']))}</dd></div><div class="wide"><dt>From Uptown Charlotte</dt><dd>${escape(fit.driveLabel)}</dd></div><div class="wide"><dt>Flat usable footprint</dt><dd>${fit.terrainVerified?'Documented — see evidence':'Not verified'}${row['Usable Flat Acres']?` · ${escape(row['Usable Flat Acres'])} recorded acres`:''}</dd></div></dl>
      ${fit.failures.length?`<p class="conflicts">${escape(fit.failures.slice(0,2).map(check=>check.note).join(' · '))}</p>`:''}
      <p class="source-note">${escape(fresh.label)}${fresh.date?` · ${escape(date(fresh.date))}`:''}. Confirm availability with the broker.</p>
      <details><summary>Required checks${fit.unknown.length?` · ${fit.unknown.length} unverified`:''}</summary>${checks}<p class="source-note">${escape(fit.expansionLabel)}. ${fit.score}/100 documented research points; not an appraisal.</p></details>
      <details><summary>Source notes &amp; next steps</summary><p>${escape(row['Listing Notes']||'No source notes recorded.')}</p><p><strong>Recorded status:</strong> ${escape(row.Status||'Unverified')}</p><p>${escape(row['Listing Verification Status']||'Source details require review.')}</p><p><strong>Next step:</strong> ${escape(row['Next Due Diligence']||'Confirm flat footprint, arena/grass layout, access, drainage, permitted use and availability.')}</p></details>
      <div class="card-links">${url?`<a class="button" href="${escape(url)}" target="_blank" rel="noopener noreferrer">View source</a>`:''}<a class="button secondary" href="${escape(route(row))}" target="_blank" rel="noopener noreferrer">Check drive</a></div>
      <button class="secondary save-property" type="button" data-save-id="${escape(key)}" aria-pressed="${saved.has(key)}">${saved.has(key)?'Saved on this device':'Save for review'}</button>
      ${votesAvailable?`<div class="team-vote" data-vote-panel="${key}"><span>Team preference — not suitability evidence</span><div><button type="button" data-vote-id="${key}" data-vote="1" aria-pressed="${Number(userVotes[key])===1}" ${pendingVotes.has(key)?'disabled':''}>Upvote</button> <button type="button" data-vote-id="${key}" data-vote="-1" aria-pressed="${Number(userVotes[key])===-1}" ${pendingVotes.has(key)?'disabled':''}>Downvote</button></div><span role="status" data-vote-summary>${Number(tally.up)||0} up · ${Number(tally.down)||0} down</span></div>`:''}</div></article>`;
  }
  function renderMap(items){
    const located=items.filter(item=>item.fit.location);
    $('mapStatus').textContent=`${located.length} of ${items.length} visible records have coordinates. Source coordinates still need parcel-level confirmation.`;
    if(typeof window.L==='undefined'){$('mapStatus').textContent+=' Map unavailable; each property still has a driving-route link.';return;}
    const L=window.L;
    if(!map){map=L.map('investorMap',{scrollWheelZoom:false}).setView([35.02,-80.99],9);const tiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);tiles.on('tileerror',()=>{$('mapStatus').textContent='Map tiles could not load. Driving-route links remain available.';});markers=L.layerGroup().addTo(map);}
    markers.clearLayers();const origin=[snapshot.brief.origin.latitude,snapshot.brief.origin.longitude],bounds=[origin];L.marker(origin).addTo(markers).bindPopup('Uptown Charlotte — drive origin');
    items.forEach(({row,fit},index)=>{if(!fit.location)return;const position=[fit.location.lat,fit.location.lng];bounds.push(position);L.marker(position).addTo(markers).bindPopup(`<strong>${escape(name(row))}</strong><p>${escape(fit.label)}</p><a href="#property-${id(row)}-${index}">View checks</a>`);});
    if(bounds.length>1)map.fitBounds(bounds,{padding:[25,25],maxZoom:11});else map.setView([35.02,-80.99],9);setTimeout(()=>map.invalidateSize(),100);
  }
  function render(){
    if(!snapshot)return;const items=filtered();
    $('investorStats').innerHTML=[['Documented fit',entries.filter(e=>e.fit.status==='eligible').length],['Needs verification',entries.filter(e=>e.fit.status==='research').length],['Outside brief',entries.filter(e=>e.fit.status==='outside').length],['Old / unknown source reviews',entries.filter(e=>e.fresh.state!=='recent').length]].map(([label,count])=>`<div class="stat"><span>${label}</span><strong>${count}</strong></div>`).join('');
    $('resultCount').textContent=`${items.length} shown · ${entries.length} tracked · saved preferences apply only to this device`;
    $('propertyGrid').innerHTML=items.map(card).join('');$('investorEmpty').hidden=items.length>0;
    $('emptyTitle').textContent=$('researchView').value==='saved'?'No saved properties in this view':'No properties in this view';
    $('emptyMessage').textContent=entries.length?'Saved records may be outside the brief, or your filters may hide them. No active matches is not proof that suitable land does not exist. Review the archive or browse the wider market below.':'No research records loaded yet. Source failures and empty searches are reported separately; the page will not invent a shortlist.';
    renderMap(items);
  }
  async function load(){
    const ticket=++sequence;$('investorLoading').hidden=false;$('propertyGrid').setAttribute('aria-busy','true');
    try{
      let next,origin='Latest repository snapshot';
      try{next=D.validate(await request(`${RAW}data/property-research.json?t=${Date.now()}`));}
      catch{
        try{next=D.validate(await request(`/data/property-research.json?t=${Date.now()}`));origin='Deployed fallback — latest repository snapshot unavailable';}
        catch{
          const [brief,csv]=await Promise.all([request(`${RAW}data/property-search-brief.json?t=${Date.now()}`),request(`${RAW}data/charlotte_polo_properties.csv?t=${Date.now()}`,{text:true})]);
          const rows=R.parseCSV(csv).filter(row=>!R.isAudit(row));
          next=D.validate({schemaVersion:2,generatedAt:new Date().toISOString(),brief,properties:rows,health:{status:'not-run',message:'The published research snapshot is unavailable. Showing the saved ledger; no new source check is implied.',sources:[],pausedPortals:brief.pausedPortals},latestListingReviewAt:rows.map(row=>row['Listing Checked At']||row['Listing Verified At']||row['Last Researched']||'').sort().at(-1)||null});origin='Ledger fallback — health snapshot unavailable';
        }
      }
      if(ticket!==sequence)return null;
      snapshot=next;entries=next.properties.map(row=>({row,fit:R.evaluate(row,next.brief),fresh:D.freshness(row,next.brief.listingStaleDays||30)}));sourceHealth(origin);render();return next;
    }catch(error){if(ticket===sequence)notice(`Saved research could not be loaded (${error.message}). Any visible results are the last successfully loaded snapshot. Reload results to retry.`,'error');return null;}
    finally{if(ticket===sequence){$('investorLoading').hidden=true;$('propertyGrid').setAttribute('aria-busy','false');}}
  }
  async function getRuns(){const data=await request(RUNS);return Array.isArray(data.workflow_runs)?data.workflow_runs:[];}
  async function refreshWorkflowLabel(){try{$('workflowStatus').textContent=D.workflowLabel(D.latestRun(await getRuns()));}catch{$('workflowStatus').textContent='Live workflow status unavailable. The source-health report above is the last saved result.';}}
  function stopWatching(){clearTimeout(watchTimer);watch=null;write('cltPoloResearchWatch',null,true);agent.disabled=false;agent.textContent='Check for new properties';}
  async function poll(){
    if(!watch)return;const current=watch;
    if(Date.now()-current.requestedAt>12*60000){notice('Stopped checking progress after 12 minutes. This does not mean the workflow stopped; reload results or review workflow details.');stopWatching();return;}
    try{
      const runs=await getRuns();if(watch!==current)return;
      const run=current.runId?runs.find(r=>r.id===current.runId):D.dispatchedRun(runs,current.requestedAt,current.baseline);
      if(run){current.runId=run.id;write('cltPoloResearchWatch',current,true);$('workflowStatus').textContent=D.workflowLabel(run);
        if(run.status==='completed'){
          const loaded=await load();if(watch!==current)return;
          if(loaded&&String(loaded.workflowRunId)===String(run.id)){
            notice(`${D.workflowLabel(run)}. ${loaded.health.message||'Review the source-health report.'}`,run.conclusion==='success'?'info':'error');stopWatching();return;
          }
          current.publishChecks=(current.publishChecks||0)+1;
          if(current.publishChecks>=4){notice(`${D.workflowLabel(run)}. The matching results snapshot is not available yet; existing data is retained.`,'error');stopWatching();return;}
          notice('The job finished. Checking for its published results; saved data is still displayed.');
        }else notice(D.workflowLabel(run)+'. You can continue reviewing saved properties.');
      }else notice('Refresh request accepted. Waiting for a new workflow run; source data has not changed yet.');
    }catch(error){notice(`Live progress could not be checked (${error.message}). The refresh may still be running; saved research remains available.`,'error');stopWatching();return;}
    if(watch===current)watchTimer=setTimeout(poll,30000);
  }
  agent.addEventListener('click',async()=>{
    if(watch)return;agent.disabled=true;agent.textContent='Starting source check…';const requestedAt=Date.now();let baseline=[];
    try{baseline=(await getRuns()).map(run=>run.id);}catch{/* Timestamp still prevents attaching to an old completed run. */}
    try{
      await request(agent.dataset.refreshEndpoint,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify({source:'investor-dashboard'})});
      watch={requestedAt,baseline};write('cltPoloResearchWatch',watch,true);agent.textContent='Source check in progress';notice('Request accepted — not a completed search. Progress will appear here while this page is open.');watchTimer=setTimeout(poll,5000);
    }catch(error){notice(`The refresh service could not start a check (${error.message}). Saved research is unchanged. Review source health or reload results.`,'error');stopWatching();}
  });
  async function loadVotes(){try{const data=await request(agent.dataset.voteEndpoint);if(!data||!data.votes||typeof data.votes!=='object'||Array.isArray(data.votes))throw new Error('Invalid vote response');tallies=data.votes;votesAvailable=true;$('voteServiceStatus').textContent='Shared voting is available. Votes are preferences, not suitability evidence.';}catch{votesAvailable=false;$('voteServiceStatus').textContent='Shared voting is unavailable from the deployed service. Save for review still works locally on this device.';}render();}
  async function vote(button){
    const key=button.dataset.voteId;if(pendingVotes.has(key))return;pendingVotes.add(key);const before=[1,-1].includes(Number(userVotes[key]))?Number(userVotes[key]):0,next=before===Number(button.dataset.vote)?0:Number(button.dataset.vote);const panel=button.closest('[data-vote-panel]');panel.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{const data=await request(agent.dataset.voteEndpoint,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify({propertyId:key,vote:next,previousVote:before})});if(!data?.votes?.[key])throw new Error('No updated totals');tallies[key]=data.votes[key];if(next)userVotes[key]=next;else delete userVotes[key];write('cltPoloPropertyVotes',userVotes);pendingVotes.delete(key);render();}
    catch(error){panel.querySelector('[data-vote-summary]').textContent=`Vote was not saved (${error.message}).`;}
    finally{pendingVotes.delete(key);panel.querySelectorAll('button').forEach(b=>b.disabled=false);}
  }
  $('propertyGrid').addEventListener('click',event=>{
    const save=event.target.closest('[data-save-id]');if(save){const key=save.dataset.saveId;if(saved.has(key))saved.delete(key);else saved.add(key);write('cltPoloSavedResearch',[...saved]);render();return;}
    const button=event.target.closest('button[data-vote-id]');if(button&&!button.disabled)vote(button);
  });
  ['researchView','terrainFilter','sortFilter'].forEach(key=>$(key).addEventListener('change',render));
  let searchTimer;$('investorSearch').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(render,120);});
  $('refreshInvestorData').addEventListener('click',()=>{load();refreshWorkflowLabel();});
  function reset(view='active'){$('researchView').value=view;$('terrainFilter').value='';$('investorSearch').value='';render();}
  $('showOutside').addEventListener('click',()=>reset('outside'));$('resetFilters').addEventListener('click',()=>reset());
  document.querySelector('.map-details').addEventListener('toggle',()=>{if(map)setTimeout(()=>map.invalidateSize(),100);});
  function unlock(){
    if(!R||!D){$('investorCodeError').hidden=false;$('investorCodeError').textContent='Research scripts could not load. Reload the page to retry.';return;}
    $('investorLock').hidden=true;$('investorDashboard').hidden=false;load();loadVotes();refreshWorkflowLabel();
    const resume=read('cltPoloResearchWatch',true);if(resume&&Number.isFinite(resume.requestedAt)&&Array.isArray(resume.baseline)&&Date.now()-resume.requestedAt<12*60000){watch=resume;agent.disabled=true;agent.textContent='Checking existing refresh';poll();}
  }
  $('investorCodeForm').addEventListener('submit',event=>{event.preventDefault();if($('investorCode').value.trim()==='cltpolo123!'){try{sessionStorage.setItem('cltPoloInvestorAccess','true');}catch{}$('investorCodeError').hidden=true;unlock();}else{$('investorCodeError').hidden=false;$('investorCode').value='';$('investorCode').focus();}});
  try{if(sessionStorage.getItem('cltPoloInvestorAccess')==='true')unlock();}catch{/* Gate works without browser storage. */}
})();
