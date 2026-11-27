// Exercise the real input handlers without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/app.js', 'utf8');
const inputCode = source.slice(source.indexOf('async function startExtraction'), source.indexOf('$("download").onclick'));

function setup() {
  const nodes = {};
  const calls = [];
  const context = {
    $: id => nodes[id] ??= {value:'', disabled:false, textContent:'', listeners:{},
      addEventListener(type, fn) { this.listeners[type] = fn; },
      dispatchEvent() {}, classList:{toggle() {}}},
    request: async (url, options) => {
      calls.push({url, options});
      if (url.endsWith('/status')) return {csrf:'token'};
      if (url === '/ocr') return {text:'Page 1\nKeyboard has 88 keys.'};
      return {entities:[]};
    },
    FormData: class { append(name, file) { this[name] = file; } },
    Event: class {}, confirm:()=>true, setInterval:()=>1, clearInterval:()=>{},
    structuredClone, Date, original:null, draft:null, sourceText:'', render:()=>{},
  };
  vm.createContext(context);
  vm.runInContext(inputCode, context);
  return {context, nodes, calls};
}

(async () => {
  let {context, nodes, calls} = setup();
  context.$('source').value = 'Typed text';
  await context.startExtraction();
  assert.deepEqual(calls.map(c=>c.url), ['/api/extract']);
  assert.equal(JSON.parse(calls[0].options.body).text, 'Typed text');

  ({context, nodes, calls} = setup());
  const file = {name:'manual.pdf', size:100};
  await context.startExtraction(file);
  assert.deepEqual(calls.map(c=>c.url), ['/api/graph/status', '/ocr', '/api/extract']);
  assert.equal(calls[1].options.body.file, file);
  assert.equal(calls[1].options.headers['X-Anywikia-CSRF'], 'token');
  assert.equal(JSON.parse(calls[2].options.body).text, nodes.source.value);
  assert.equal(context.sourceText, nodes.source.value);
  assert.equal(nodes.run.disabled, false);

  ({context, nodes, calls} = setup());
  context.request = async url => { calls.push(url); if(url.endsWith('/status')) return {csrf:'token'}; throw Error('OCR unavailable'); };
  await context.startExtraction(file);
  assert.deepEqual(calls, ['/api/graph/status', '/ocr']);
  assert.equal(nodes.status.textContent, 'OCR unavailable');
  assert.equal(nodes.run.disabled, false);

  ({context, nodes, calls} = setup());
  context.request = async url => { calls.push(url); return url.endsWith('/status') ? {csrf:'token'} : {text:'x'.repeat(20001)}; };
  await context.startExtraction(file);
  assert.equal(nodes.source.value.length, 20001);
  assert.equal(calls.includes('/api/extract'), false);
  assert.match(nodes.status.textContent, /20,000/);

  ({context, nodes, calls} = setup());
  await context.startExtraction({name:'bad.exe', size:20});
  assert.equal(calls.length, 0);
  context.draft = {entities:[{name:'existing review'}]};
  context.confirm = () => false;
  await context.startExtraction(file);
  assert.equal(calls.length, 0);
  assert.equal(context.draft.entities[0].name, 'existing review');

  // Both drop and file-picker events call the same pipeline.
  const received = [];
  context.startExtraction = file => received.push(file);
  nodes['source-file'].listeners.change({target:{files:[file]}});
  nodes['upload-zone'].listeners.drop({preventDefault(){},dataTransfer:{files:[file]}});
  assert.deepEqual(received, [file, file]);
  console.log('Source input checks passed: text, upload, drop, OCR failure, length limit and draft protection.');
})().catch(error => { console.error(error); process.exitCode = 1; });
