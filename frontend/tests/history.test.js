import 'fake-indexeddb/auto';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createStore } from '../src/chat/store.js';
const fresh = () => createStore(`test-${crypto.randomUUID()}`);
const input = (id = 'one') => ({ id, mode:'warehouse', country:'UG', text:'Group Performance Report August 2026' });

test('persists full structured response, title and draft across new store instance', async () => {
    const name = crypto.randomUUID(), a = createStore(name);
    const job = await a.begin(input());
    const result = { report:{report_id:'snapshot',metrics:{par:0},sections:[{title:'Example'}]}, rows:[{amount:100}], credit_score:true, data:{percentage:80} };
    await a.finish('one', job.requestId, result);
    await a.patch('one',{draft:'Now July',title:'Renamed'});
    const b = createStore(name);
    assert.equal((await b.get('one')).draft, 'Now July');
    assert.equal((await b.list())[0].title,'Renamed');
    assert.deepEqual((await b.messages('one'))[1].response,result);
});
test('atomic pending guard stops concurrent tabs and double submit', async () => {
    const a = fresh();
    const results = await Promise.allSettled([a.begin(input()),a.begin(input())]);
    assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
    assert.equal((await a.messages('one')).length,2);
});
test('late response never revives deleted chat', async () => {
    const a=fresh(),job=await a.begin(input());
    await a.remove('one');
    assert.equal(await a.finish('one',job.requestId,{answer:'late'}),false);
    assert.deepEqual(await a.list(),[]); assert.deepEqual(await a.messages('one'),[]);
    await assert.rejects(a.begin(input()),/deleted/);
});
test('retry reuses message and ignores original request result', async () => {
    const a=fresh(),job=await a.begin(input());
    await a.finish('one',job.requestId,null,'interrupted','Interrupted');
    const retry=await a.begin({...input(),retryId:job.reply.id});
    assert.equal((await a.messages('one')).length,2);
    assert.notEqual(job.requestId,retry.requestId);
    assert.equal(await a.finish('one',job.requestId,{answer:'old'}),false);
    await a.finish('one',retry.requestId,{answer:'new'});
    assert.equal((await a.messages('one'))[1].response.answer,'new');
});
test('chat switch preserves separate pending responses and metadata patches', async () => {
    const a=fresh(),one=await a.begin(input()),two=await a.begin(input('two'));
    await a.patch('one',{title:'Title',draft:'draft',mode:'ask'});
    await a.finish('two',two.requestId,{answer:'two'});
    await a.finish('one',one.requestId,{answer:'one'});
    assert.equal((await a.messages('one'))[1].text,'one');
    assert.equal((await a.messages('two'))[1].text,'two');
    assert.equal((await a.get('one')).mode,'warehouse');
    assert.equal((await a.get('one')).draft,'draft');
});
test('new chat leaves history intact and truncates unicode title to 60 characters', async () => {
    const a=fresh();await a.begin({...input(),text:'ক'.repeat(80)});await a.begin(input('two'));
    assert.equal((await a.list()).length,2); assert.equal([...(await a.get('one')).title].length,60);
    await a.saveSetting('newDraft',{text:'draft',mode:'ask',country:'ALL'});
    assert.equal((await a.setting('newDraft')).text,'draft');
});

test('failed transaction preserves existing history and creates no partial message', async () => {
    const a=fresh(); const first=await a.begin(input()); await a.finish('one',first.requestId,{answer:'keep'});
    const original=IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put=function(...args) { if(this.name==='messages') throw new DOMException('Quota reached','QuotaExceededError'); return original.apply(this,args); };
    try { await assert.rejects(a.begin(input('quota')), {name:'QuotaExceededError'}); }
    finally { IDBObjectStore.prototype.put=original; }
    assert.equal((await a.list()).length,1); assert.equal((await a.messages('one'))[1].text,'keep'); assert.equal((await a.messages('quota')).length,0);
});
