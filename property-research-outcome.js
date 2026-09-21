/* Pure result presentation. A new run/report is not a new or reverified listing. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PoloResearchOutcome=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function count(value){return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0?value:null;}
  function checkTime(value){const t=typeof value==='string'?Date.parse(value):NaN;return Number.isFinite(t)?new Intl.DateTimeFormat('en-US',{dateStyle:'medium',timeStyle:'long',timeZone:'America/New_York'}).format(new Date(t)):'Not established';}
  function summary(health){
    const h=health||{},added=count(h.rowsAdded),changed=count(h.rowsChanged),checked=count(h.listingsChecked);
    if(added===null||changed===null||checked===null)return 'Listing-change counts are unavailable in this report. Do not assume a successful update.';
    const counts=`${added} new · ${changed} changed · ${checked} listing pages checked.`;
    if(['blocked','error'].includes(h.status))return `Source check failed. ${counts} Saved research is retained; this is not a completed market search.`;
    if(checked===0&&added===0&&changed===0)return `No listing updates. ${counts} No usable listing data was collected; this does not mean no suitable land exists.`;
    if(added===0&&changed===0)return `No listing changes. ${counts} Source coverage may be limited; site suitability still needs verification.`;
    return `${counts} Newly collected records are research leads, not verified polo sites.`;
  }
  function newer(current,candidate){
    if(!current)return candidate;
    const a=Date.parse(current.generatedAt),b=Date.parse(candidate.generatedAt);
    return Number.isFinite(a)&&Number.isFinite(b)&&a>b?current:candidate;
  }
  function reloadMessage(before,after){
    const same=before&&String(before.workflowRunId||before.generatedAt)===String(after.workflowRunId||after.generatedAt);
    return `${same?'Latest report reloaded; no newer report is published.':'Published report loaded.'} ${summary(after.health)}`;
  }
  return {count,checkTime,summary,newer,reloadMessage};
});
