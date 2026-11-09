import test from 'node:test';
import assert from 'node:assert/strict';
import {dateKey} from './domain.js';
import {toUTCTime} from './observation-data.js';
test('event editor uses UTC and preserves the instant of offset timestamps',()=>{
 assert.equal(toUTCTime('2026-11-09T01:15:00+03:00'),'2026-11-08T22:15');
 assert.equal(new Date(`${toUTCTime('2026-11-09T01:15:00+03:00')}Z`).toISOString(),'2026-11-08T22:15:00.000Z');
 assert.equal(toUTCTime(null),'');assert.equal(toUTCTime('bad'),'');
 assert.equal(dateKey(new Date('2026-11-08T23:59:59Z')),'2026-11-08');
});
