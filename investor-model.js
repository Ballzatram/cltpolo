/* Pure feasibility arithmetic. No network, storage, recommendations or hidden site defaults. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PoloInvestment = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const known = n => typeof n === 'number' && Number.isFinite(n);
  const sum = rows => rows.reduce((n, r) => n + r.amount, 0);
  const moneyRow = (label, amount, note = '') => ({label, amount, note});
  function inputs(data, overrides = {}, preset = 'base') {
    const result = {};
    for (const f of data.fields) {
      const v = Object.prototype.hasOwnProperty.call(overrides, f.id) ? overrides[f.id] : f[preset];
      if (!known(v) || v < f.min || v > f.max) throw new Error(`Invalid ${f.label}: expected ${f.min}–${f.max}.`);
      result[f.id] = v;
    }
    for (const k of ['stalls','horses','reserveStalls','groupSize']) if (!Number.isInteger(result[k])) throw new Error(`${k} must be a whole number.`);
    if (result.horses + result.reserveStalls > result.stalls) throw new Error('Owned horses plus reserve stalls exceed total stalls.');
    return result;
  }
  function validateSite(data, site) {
    const next = {id:String(site.id),name:String(site.name || 'Unnamed site').slice(0,150),address:String(site.address || '').slice(0,500),county:String(site.county || '').slice(0,150),notes:String(site.notes || '').slice(0,10000)};
    if (!['','NC','SC'].includes(site.state)) throw new Error('State must be NC, SC, or unselected.');
    next.state = site.state;
    const limits = {acres:10000,flatAcres:10000,drive:300,landPrice:100000000,taxValue:200000000,taxRate:1000,taxRatio:100,agValue:200000000,agRatio:100,taxFees:1000000,rollback:10000000,capexAdjustment:50000000,annualAdjustment:1000000};
    for (const [k,max] of Object.entries(limits)) {
      let v = site[k];
      if (['taxRatio','agValue','agRatio','taxFees','rollback','capexAdjustment','annualAdjustment'].includes(k) && v == null) v = k === 'taxRatio' ? 6 : k === 'agRatio' ? 4 : 0;
      if (v != null && (!known(v) || v > max || v < (k.includes('Adjustment') ? -max : 0))) throw new Error(`Invalid site value: ${k}.`);
      next[k] = v == null ? null : v;
    }
    if (known(next.flatAcres) && known(next.acres) && next.flatAcres > next.acres) throw new Error('Usable flat acres cannot exceed parcel acres.');
    if (!['wood','steel','hybrid'].includes(site.fenceType)) throw new Error('Invalid fence type.');
    if (!data.scenarios[site.scenario]) throw new Error('Invalid demand scenario.');
    next.fenceType = site.fenceType; next.scenario = site.scenario;
    next.diligence = {};
    for (const [key] of data.diligence) next.diligence[key] = site.diligence?.[key] === true;
    next.inputs = inputs(data, site.inputs || {});
    return next;
  }
  function debtService(principal, rate, years) {
    if (!principal) return 0;
    const r = rate / 1200, months = years * 12;
    return r ? principal * r / (1 - Math.pow(1 + r, -months)) * 12 : principal / years;
  }
  function tax(site) {
    if (!['NC','SC'].includes(site.state) || !known(site.taxValue) || !known(site.taxRate)) return null;
    return (site.state === 'NC' ? (site.taxValue + site.agValue)*site.taxRate/100 : (site.taxValue*site.taxRatio/100 + site.agValue*site.agRatio/100)*site.taxRate/1000) + site.taxFees;
  }
  function build(a, site) {
    const fenceRate = site.fenceType === 'wood' ? a.woodRate : site.fenceType === 'steel' ? a.steelRate : a.woodRate * (1-a.steelShare/100) + a.steelRate * a.steelShare/100;
    const rows = [moneyRow('Barn shell / foundations / erection',a.barnSqft*a.barnRate),moneyRow('Stall systems / fit-out',a.stalls*a.stallRate),moneyRow('Outdoor arena, not covered',a.arena),moneyRow('Site grading outside arena',a.earthworks),moneyRow('Barn utilities / water / septic',a.utilities),moneyRow('Driveways / parking / access',a.access),moneyRow('Guest pavilion / public restrooms',a.guest),moneyRow('Separate storage',a.storage),moneyRow('Pasture / run-in shelters',a.pasture),moneyRow(`${site.fenceType} fence · ${a.fenceFeet.toLocaleString()} ft`,a.fenceFeet*fenceRate),moneyRow('Gates / hardware / paddock water',a.gates),moneyRow('Equipment / trailer / tools',a.equipment),moneyRow('Site-specific hard-cost adjustment',site.capexAdjustment,'Negative only for documented scope removed or reusable assets; do not credit purchase value twice.')];
    const hard = sum(rows);
    if (hard < 0) throw new Error('Site cost credit exceeds the entire hard-cost budget.');
    const soft = hard*a.softPct/100, contingency=(hard+soft)*a.contingencyPct/100;
    rows.push(moneyRow('Design / permitting / professional fees',soft),moneyRow('Construction contingency',contingency),moneyRow('Club horse purchases',a.horses*a.horsePrice),moneyRow('Horse exam / transport / intake',a.horses*a.horseIntake),moneyRow('Tack / protective / learner equipment',a.horses*a.tack),moneyRow('Preopening hiring / training / launch',a.preOpen),moneyRow('Construction carrying / finance allowance',a.carry));
    return {rows,hard,soft,contingency,total:sum(rows),fenceRate};
  }
  function horseCare(a) {
    return [moneyRow('Grass hay',365*a.grassLbs*a.grassPrice/(1-a.forageWaste/100)),moneyRow('Alfalfa component',365*a.alfalfaLbs*a.alfalfaPrice/(1-a.forageWaste/100)),moneyRow('Concentrate / grain',365*a.grainLbs*a.grainPrice),moneyRow('Bedding',52*a.beddingBags*a.beddingPrice),moneyRow('Farrier / shoeing',52/a.farrierWeeks*a.farrierVisit),moneyRow('Routine vet / dental / tests',a.vet),moneyRow('Emergency medical provision',a.emergency),moneyRow('Grooming / fly protection / supplies',a.consumables),moneyRow('Variable drinking / wash water',365*a.waterGallons/1000*a.waterPrice)];
  }
  function operate(data, a, site, ramp=1, year=1) {
    const d=data.scenarios[site.scenario], warnings=[], inflation=(1+a.costGrowth/100)**(year-1), price=(1+a.priceGrowth/100)**(year-1), weather=1-a.weather/100;
    const horseRows=horseCare(a), care=sum(horseRows)*a.horses;
    const wages=a.manager+a.trainer+a.groomFte*2080*a.groomWage;
    const fixedRows=[moneyRow('Club horse care (owned horses only)',care),moneyRow('General manager / founder replacement',a.manager),moneyRow('Head instructor / trainer',a.trainer),moneyRow('Groom / barn staff wages',a.groomFte*2080*a.groomWage),moneyRow('Employer burden / coverage',wages*a.burdenPct/100),moneyRow('Insurance',a.insurance),moneyRow('Fixed utilities / irrigation / fuel',a.utilityAnnual),moneyRow('Routine repairs / grounds',a.maintenance),moneyRow('Manure / waste',a.manure),moneyRow('Marketing / sales',a.marketing),moneyRow('Legal / accounting / systems',a.admin),moneyRow('Site-specific annual adjustment',site.annualAdjustment)].map(r=>({...r,amount:r.amount*inflation}));
    const fixed=sum(fixedRows), taxValue=tax(site), taxForCalc=(taxValue ?? 0)*inflation;
    if (fixed < 0) throw new Error('Annual credit exceeds all fixed operating costs.');
    const players=d.players*ramp, requestedMatches=d.matches*ramp, matches=Math.min(requestedMatches,a.eventDays)*weather;
    const otherRequested=(d.corporate+d.private)*ramp;
    const eventFactor=otherRequested ? Math.min(1,Math.max(0,a.eventDays-requestedMatches)/otherRequested) : 1;
    const corporate=d.corporate*ramp*eventFactor*weather, privateEvents=d.private*ramp*eventFactor*weather;
    if (eventFactor<1 || requestedMatches>a.eventDays) warnings.push('Requested events exceed the shared calendar: realized event revenue has been capped. More event dates need staffing, setup and permit validation.');
    const horseCapacity=a.horses*a.horseAvailability/100*a.horseSlots*a.weeks*weather;
    const instructorCapacity=a.instructorSlots*Math.min(a.groupSize,Math.floor(a.horses*a.horseAvailability/100))*a.weeks*weather;
    const capacity=Math.min(horseCapacity,instructorCapacity), included=players*a.memberMounts, corporateMounts=corporate*a.corpMounted;
    const mountedDemand=included+corporateMounts+d.lessons*ramp*weather;
    // Reserve included member service before new business. Remaining paid services share capacity proportionally.
    const paidDemand=corporateMounts+d.lessons*ramp*weather, capacityFactor=paidDemand ? Math.min(1,Math.max(0,capacity-included)/paidDemand) : 1;
    const lessons=d.lessons*ramp*weather*capacityFactor, realizedCorporate=corporate*capacityFactor;
    if (mountedDemand>capacity) warnings.push('Mounted demand exceeds provisional horse/instructor capacity: lessons and corporate packages have been reduced proportionally. Member mount promises still need individual scheduling.');
    if (included>capacity) warnings.push('Included member mounts alone exceed capacity. This scenario cannot deliver its stated membership promise.');
    const boardingSlots=Math.max(0,a.stalls-a.horses-a.reserveStalls), boarders=boardingSlots*d.boardOccupancy*ramp;
    const paidVisits=d.audience*d.visits*ramp*(d.matches ? matches/(d.matches*ramp || 1) : 0);
    const rows=[];
    function revenue(label,gross,direct,note) { const fees=gross*a.paymentPct/100; rows.push({label,gross,direct,fees,contribution:gross-direct-fees,note}); }
    revenue('Player dues',players*a.dues*price,0,'Average paid-player equivalents; included mount capacity reserved. No unlimited horse use.');
    revenue('Polo spectator admissions',paidVisits*a.ticket*price,matches*a.matchCost*inflation,'Unique audience × repeat paid visits, adjusted for completed events. No duplicate social membership revenue.');
    revenue('Lessons / introductory experiences',lessons*a.lessonPrice*price,lessons*a.lessonPrice*a.lessonVariable/100*inflation,'Completed rider-sessions after cancellations and capacity cap; not unique customers.');
    revenue('Full-care boarding',boarders*a.boardPrice*12*price,boarders*a.boardVariable*12*inflation,'Occupied stall equivalents; customer vet/farrier excluded from package assumption.');
    revenue('Corporate experiences',realizedCorporate*a.corporatePrice*price,realizedCorporate*a.corporatePrice*a.corporateVariable/100*inflation,'Calendar- and horse-capacity constrained. Includes all direct delivery allowance.');
    revenue('Private / partner events',privateEvents*a.privatePrice*price,privateEvents*a.privatePrice*a.privateVariable/100*inflation,'Unmounted experience use only; dedicated wedding/lodging expansion not assumed.');
    revenue('Sponsorship',d.sponsorship*ramp*price,d.sponsorship*ramp*a.sponsorVariable/100*inflation,'Uncommitted planning assumption; excluded from cautious case. No donations or grants.');
    const gross=rows.reduce((t,r)=>t+r.gross,0), contribution=rows.reduce((t,r)=>t+r.contribution,0), beforeTax=contribution-fixed;
    const debt=debtService(a.debt,a.interest,a.term)*Math.min(12,Math.max(0,a.term*12-(year-1)*12))/12, replacement=a.replacement*inflation;
    const cashBeforeTax=beforeTax-debt-replacement;
    const poloContribution=rows.slice(0,2).reduce((t,r)=>t+r.contribution,0);
    const poloGap=fixed+taxForCalc+debt+replacement-poloContribution;
    const incrementalMargin=a.corporatePrice*price*(1-a.paymentPct/100)-a.corporatePrice*a.corporateVariable/100*inflation;
    const extraEvents=incrementalMargin>0 ? Math.ceil(Math.max(0,-(cashBeforeTax-taxForCalc))/incrementalMargin) : null;
    if (extraEvents && extraEvents+matches+realizedCorporate+privateEvents>a.eventDays*weather) warnings.push('Break-even extra-event requirement exceeds unused calendar capacity at the current assumptions; adding sales alone is not a viable fix.');
    if (taxValue===null) warnings.push('Property taxes are missing: displayed operating/cash subtotals exclude real-estate tax. All-in site cash flow remains unresolved.');
    return {rows,horseRows,care,wages,fixedRows,fixed,propertyTax:taxValue===null?null:taxForCalc,gross,contribution,beforeTax,operating:taxValue===null?null:beforeTax-taxForCalc,debt,replacement,cashBeforeTax,cash:taxValue===null?null:cashBeforeTax-taxForCalc,poloContribution,poloGap,extraEvents,capacity,mountedDemand,lessons,corporate:realizedCorporate,privateEvents,matches,boarders,boardingSlots,players,paidVisits,warnings};
  }
  function evaluate(data,rawSite) {
    const site=validateSite(data,rawSite), a=site.inputs, capex=build(a,site), stable=operate(data,a,site);
    const forecast=data.ramps.map((r,i)=>({year:i+1,ramp:r,...operate(data,a,site,r,i+1)}));
    const reserve=(stable.fixed+(stable.propertyTax ?? 0)+stable.debt)*a.reserveMonths/12;
    const knownCapital=capex.total+reserve;
    const acquisition=known(site.landPrice)?site.landPrice*(1+a.closingPct/100)+site.rollback:null;
    const total=acquisition===null || stable.propertyTax===null?null:knownCapital+acquisition;
    if (total!==null && a.debt>total) throw new Error('Term debt exceeds modeled total uses.');
    const y1=forecast[0]; let cumulative=0;
    const monthly=data.seasonality.map((weight,i)=> {
      // Dues and boarding contribution spread evenly. Other contribution follows an explicit illustrative calendar.
      const recurring=y1.rows[0].contribution+y1.rows[3].contribution;
      const contribution=recurring/12+(y1.contribution-recurring)*weight;
      const cash=contribution-(y1.fixed+(y1.propertyTax??0)+y1.debt+y1.replacement)/12;
      cumulative+=cash; return {month:i+1,cash,cumulative,closingReserve:reserve+cumulative};
    });
    const risks=[...stable.warnings];
    if (site.landPrice===null) risks.push('Land purchase and acquisition costs not entered. No all-in project price or equity requirement is established.');
    if (site.drive!==null && site.drive>45) risks.push('Recorded drive exceeds the 45-minute brief. Do not let a financial score override this location gate.');
    if (site.acres!==null && site.acres<20) risks.push('Recorded parcel is below the 20-acre minimum.');
    if (!site.diligence.flat) risks.push('Flat contiguous footprint and arena/grass layout have not been documented.');
    if (!site.diligence.zoning) risks.push('Commercial uses, event capacity and infrastructure approvals remain unverified.');
    const burn5=forecast.reduce((n,r)=>n+(r.cash??r.cashBeforeTax),0);
    if (reserve+burn5<0) risks.push('Five-year cumulative cash losses exceed the opening reserve in this case. Additional funding or a redesigned cost/revenue structure is required.');
    return {site,a,capex,stable,forecast,reserve,knownCapital,acquisition,total,equity:total===null?null:total-a.debt,monthly,risks,burn5,completeChecks:data.diligence.filter(([k])=>site.diligence[k]).length};
  }
  return {known,inputs,validateSite,debtService,tax,build,horseCare,operate,evaluate};
});
