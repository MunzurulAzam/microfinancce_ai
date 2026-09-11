import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contextFor } from '../src/chat/context.js';
test('context is bounded and excludes complete tables, images and credit numbers', () => {
    const messages=Array.from({length:12},(_,i)=>({sequence:i,role:i%2?'assistant':'user',status:'complete',text:'ক'.repeat(1500),response:{rows:[{secret:'NEVER_INCLUDE'}],image:'NEVER_INCLUDE'}}));
    const context=contextFor(messages);
    assert.ok(context.length<=6);assert.ok(new TextEncoder().encode(JSON.stringify(context)).length<=13500);assert.ok(!JSON.stringify(context).includes('NEVER_INCLUDE'));
    const credit=contextFor([{sequence:1,role:'assistant',status:'complete',text:'Score 90 loan 5000',response:{credit_score:true}}]);
    assert.equal(credit[0].text,'Member credit analysis returned.');
});
test('retry context excludes its user message and all later messages', () => {
    const ms=[{sequence:1,role:'user',status:'complete',text:'first'},{sequence:2,role:'assistant',status:'complete',text:'answer'},{sequence:3,role:'user',status:'complete',text:'retry me'},{sequence:4,role:'assistant',status:'interrupted',text:'error'},{sequence:5,role:'user',status:'complete',text:'later'}];
    assert.deepEqual(contextFor(ms,3).map(m=>m.text),['first','answer']);
});
