const assert = require('node:assert/strict');
const {compareClaim, decimalKey} = require('../frontend/comparison.js');
const row = (pid,value,unit) => ({property:{value:`https://keyboards.wikibase.cloud/entity/${pid}`},value:{value},...(unit ? {unit:{value:`http://www.wikidata.org/entity/${unit}`}} : {})});
const quantity={property_id:'P2',value_type:'Quantity'};
assert.equal(decimalKey('1385.00'),decimalKey('1.385e3'));
assert.notEqual(decimalKey('9007199254740992'),decimalKey('9007199254740993'));
assert.equal(compareClaim(quantity,{value:'1385',unit:'mm'},[]).status,'new');
assert.equal(compareClaim(quantity,{value:'1385',unit:'mm'},[row('P2','1385.0','Q174789')]).status,'exists');
assert.equal(compareClaim(quantity,{value:'1000',unit:'mm'},[row('P2','1385','Q174789')]).status,'conflict');
assert.equal(compareClaim(quantity,{value:'1385',unit:'mm'},[row('P2','1385','Q199')]).status,'uncertain');
assert.equal(compareClaim(quantity,{value:'138.5',unit:'cm'},[row('P2','1385','Q174789')]).status,'uncertain');
assert.equal(compareClaim({...quantity,property_id:'P1'},{value:'88',unit:'keys'},[row('P1','88.0','Q199')]).status,'exists');
assert.equal(compareClaim({property_id:'P6',value_type:'WikibaseItem'},{value_id:'Q2'},[row('P6','https://keyboards.wikibase.cloud/entity/Q2')]).status,'exists');
assert.equal(compareClaim({property_id:'P6',value_type:'WikibaseItem'},{value_id:null},[row('P6','https://keyboards.wikibase.cloud/entity/Q2')]).status,'uncertain');
assert.equal(compareClaim({property_id:'P5',value_type:'Url'},{value:'new'},[row('P5','old')]).status,'conflict');
assert.equal(compareClaim(quantity,{value:'1385',unit:'mm'},[row('P2','1','Q174789'),row('P2','1385','Q174789')]).status,'exists');
console.log('11 comparison checks passed');
const {requiresMeasurementUnit, unitValidationError} = require('../frontend/comparison.js');
for (const pid of ['P1','P8','P10','P12','P13','P14','P15','P20','P21','P22','P29']) {
  assert.equal(requiresMeasurementUnit({property_id:pid,value_type:'Quantity'}), false);
  assert.equal(unitValidationError({property_id:pid,value_type:'Quantity'}, {value:'61',unit:null}), '');
}
for (const pid of ['P2','P3','P4','P7','P16']) {
  const prop = {property_id:pid,value_type:'Quantity'};
  for (const value of ['10',0]) assert.notEqual(unitValidationError(prop,{value,unit:'  '}), '');
  for (const value of ['',null,'  ']) assert.equal(unitValidationError(prop,{value,unit:null}), '');
  assert.equal(unitValidationError(prop,{value:'10',unit:'mm'}), '');
  assert.equal(compareClaim(prop,{value:'10',unit:null},[]).status,'uncertain');
}
console.log('Count/measurement unit validation checks passed');
const {PRICE_CURRENCIES} = require('../frontend/comparison.js');
const price = {property_id:'P25',value_type:'Quantity'};
assert.deepEqual(PRICE_CURRENCIES, ['DKK','EUR','USD','GBP']);
for (const unit of PRICE_CURRENCIES) assert.equal(unitValidationError(price,{value:'500',unit}), '');
for (const unit of [null,'',' ','$','JPY','Q199']) {
  assert.notEqual(unitValidationError(price,{value:0,unit}), '');
  assert.equal(compareClaim(price,{value:'500',unit},[]).status,'uncertain');
}
assert.equal(unitValidationError(price,{value:'',unit:null}), '');
assert.equal(compareClaim(price,{value:'500',unit:'EUR'},[row('P25','500','Q199')]).status,'uncertain');
console.log('Price currency validation checks passed');
