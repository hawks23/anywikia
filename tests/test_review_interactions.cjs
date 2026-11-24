// Offline interaction checks using a minimal DOM; no browser/network required.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Node {
  constructor(tag, text='', cls='') { Object.assign(this,{tag,textContent:text,className:cls,children:[],listeners:{},disabled:false,value:'',attributes:{}}); }
  append(...nodes) { for (const node of nodes) { node.parent=this; this.children.push(node); } }
  prepend(node) { node.parent=this; this.children.unshift(node); }
  replaceChildren(...nodes) { this.children=[]; this.append(...nodes); }
  get childNodes() { return this.children; }
  get options() { return this.children; }
  setAttribute(k,v) { this.attributes[k]=v; }
  removeAttribute(k) { delete this.attributes[k]; }
  addEventListener(k,fn) { (this.listeners[k]??=[]).push(fn); }
  dispatchEvent(e) { e.target??=this; for(const fn of this.listeners[e.type]||[]) fn(e); if(e.bubbles) this.parent?.dispatchEvent(e); }
  querySelectorAll(selector) { const selectors=selector.split(',').map(s=>s.trim()); const result=[];
    for(const n of this.children) { if(selectors.some(s=>s[0]==='.' ? n.className.split(' ').includes(s.slice(1)) : n.tag===s)) result.push(n); result.push(...n.querySelectorAll(selector)); } return result; }
  querySelector(s) { return this.querySelectorAll(s)[0]; }
  closest(selector) { let n=this; while(n) { if(n.className.split(" ").includes(selector.slice(1))) return n; n=n.parent; } return null; }
  scrollIntoView() {}
}
const nodes={}; const $=id=>nodes[id]??=new Node('div');
$('verify-property').append(new Node('option'));
const context={console, $, el:(...args)=>new Node(...args), setTimeout:()=>{}, confirm:()=>true,
  Event:class {constructor(type,options={}){this.type=type;Object.assign(this,options);}},
  sourceText:'The Yamaha P-150 has 88 keys.', render:()=>{}, draft:{entities:[]}};
let inspections=0, previews=0, confirmations=0, previewClaims, failOnce=false, release;
context.request=async(url,options)=>{
  if(url.endsWith('/status')) return {ready:true,csrf:'test',properties:[{property_id:'P1',label:'keys'}]};
  const payload=JSON.parse(options.body);
  if(url.endsWith('/inspect')) { inspections++; return {statements:[{property_id:'P1',statement:'s1',subject:'kb/Q1',value:'88',replaceable:true}]}; }
  if(url.endsWith('/preview')) { previews++; previewClaims=payload.claims; return {preview_id:'p1',entity_id:payload.mode==='new'?'Q999':'Q1',summary:[{property:'P1',value:payload.claims[0].value,action:payload.claims[0].action,replaces:payload.claims[0].statement}]}; }
  if(url.endsWith('/confirm')) { confirmations++; if(failOnce){failOnce=false;throw Error('Update status uncertain');} await new Promise(resolve=>release=resolve); return {entity_id:'Q1',operation_id:'p1',verified:true}; }
  throw Error(url);
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/review-plan.js','utf8'),context);
vm.runInContext(fs.readFileSync('frontend/rdf-review.js','utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();
  const claim={value:'90',unit:'key',edited:true};
  const entity={name:'Yamaha P-150',review_match:'Q1',confirmed:true,properties:{keys:{label:'keys',property_id:'P1',value_type:'Quantity',claims:[claim]},maker:{property_id:'P6',claims:[{value:'Yamaha'}]}}};
  context.draft.entities=[entity];
  const card=new Node('details','','entity-card'), body=new Node('div'); card.append(body); $('results').append(card);
  context.attachEntityWriteControls(entity,body,card);
  const apply=card.querySelectorAll('button').find(b=>b.textContent==='Apply changes to QLever');
  const running=apply.onclick(); await tick();
  assert.equal(previewClaims.length,1,'untouched manufacturer must not be saved');
  assert.equal(previewClaims[0].action,'replace'); assert.equal(previewClaims[0].statement,'s1');
  assert.equal(apply.textContent,'Applying…'); assert.equal(apply.disabled,true);
  assert.match(card.querySelector('.save-status').textContent,/verifying/);
  release(); await running;
  assert.match(entity.save_message,/applied and verified/); assert.equal(claim.include_change,false);
  // A later edit is selectable after a successful save, with uncertain-write retry.
  claim.value='91'; claim.edited=true; claim.include_change=true; failOnce=true;
  card.dispatchEvent({type:'draftchange'});
  await apply.onclick(); assert.equal(apply.textContent,'Check previous update'); assert(entity.pending_save);
  claim.value='92'; // newer edit must not prevent resolving the prior operation
  const beforeRetry=[inspections,previews];
  const retry=apply.onclick(); await tick(); release(); await retry;
  assert.deepEqual([inspections,previews],beforeRetry,"retry must retain the original preview and statement IDs");
  assert.equal(claim.value,'92'); assert.equal(claim.include_change,true);
  assert.match(entity.save_message,/newer edits are still unsaved/);
  assert.equal(confirmations,3); assert.equal(entity.pending_save,null);
  // New records always add and include unedited extracted values.
  const newEntity={name:'New keyboard',confirmed:true,demo_added:true,properties:{keys:{property_id:'P1',label:'keys',claims:[{value:'61'}]}}};
  const payload=context.writePayload(newEntity,{statements:[]});
  assert.equal(payload.mode,'new'); assert.equal(payload.claims[0].action,'add');
  // Actual confirmation handler must expose progress and restore controls on failure.
  const appSource=fs.readFileSync('frontend/app.js','utf8');
  vm.runInContext(appSource.slice(appSource.indexOf('function recordPanel('),appSource.indexOf('// Compact mode')),context);
  let resolveMatch; const originalRequest=context.graphRequest;
  context.graphRequest=()=>new Promise(resolve=>resolveMatch=resolve);
  const matchEntity={}; let matched=false;
  const matchCard=new Node('details','','entity-card'); const editor=new Node('input'); matchCard.append(editor);
  const panel=context.recordPanel({id:'Q1'},matchEntity,()=>{matched=true;}); matchCard.append(panel);
  const button=panel.querySelector('button');
  const pendingMatch=button.onclick();
  assert.equal(button.textContent,'Confirming match…'); assert.equal(editor.disabled,true);
  assert.equal(matchCard.attributes['aria-busy'],'true');
  resolveMatch({name:'Keyboard'}); await pendingMatch;
  assert.equal(matched,true); assert.equal(editor.disabled,false); assert.equal(matchEntity.confirming_match,false);
  context.graphRequest=async()=>{throw Error('offline');};
  await button.onclick(); assert.equal(button.disabled,false); assert.equal(button.textContent,'Confirm this match');
  context.graphRequest=async()=>({name:'Korg SV-2 88'});
  const namedPanel=context.recordPanel({id:'Q34'}, {}, ()=>{});
  await tick();
  assert.equal(namedPanel.querySelector('strong').textContent,'Korg SV-2 88 (Q34)');
  context.graphRequest=originalRequest;
  console.log('Match confirmation loading and failure recovery checks passed');
  console.log('Interaction checks passed: automatic replacement, selected-only writes, progress, success, second edit, uncertain retry, new entity.');
})().catch(error=>{console.error(error);process.exitCode=1;});
