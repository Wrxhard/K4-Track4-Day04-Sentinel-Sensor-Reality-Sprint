import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statistics, settingsFromValues, packFrame, unpackFrame, frameRates, bandwidthMbps } from '../dist/metrics.js';
test('missing GPU readings remain unavailable; zero is a real measurement',()=>{
  assert.equal(statistics([null, null]).mean,null);
  assert.equal(statistics([null, 0]).mean,0);
  assert.equal(statistics([1, 3, 2, 4]).median,2.5);
});
test('actual FPS decays to zero when displayed frames stop',()=>{
  assert.equal(frameRates([{time:1500},{time:2500}],1000,3000).fps,1);
  assert.equal(frameRates([{time:1500},{time:2500}],1000,6000).fps,0);
  const highFrames=Array.from({length:45},(_,i)=>({time:3100+i*65}));
  assert.equal(frameRates(highFrames,0,6000).fps,15);
});
test('frame packets retain timestamps and binary image bytes',()=>{
  const packet=packFrame({id:1,capture_ms:5},new Uint8Array([1,2,3]));
  assert.deepEqual(unpackFrame(packet.buffer).metadata,{id:1,capture_ms:5});
  assert.deepEqual([...unpackFrame(packet.buffer).jpeg],[1,2,3]);
  assert.throws(()=>unpackFrame(new ArrayBuffer(2)));
});
test('idle and person FPS limits are validated',()=>{
  const defaults={idle_fps:2,active_fps:15,hold_seconds:1};
  assert.equal(settingsFromValues(defaults).confidence,.35);
  assert.throws(()=>settingsFromValues({...defaults,idle_fps:10,active_fps:5}));
  assert.throws(()=>settingsFromValues({...defaults,active_fps:31}));
});
test('raw bandwidth uses decimal Mbps, scales with cameras and FPS, and handles stopped frames',()=>{
  assert.equal(bandwidthMbps(1,640,480,2,24),14.7456);
  assert.equal(bandwidthMbps(1,640,480,15,24),110.592);
  assert.equal(bandwidthMbps(2,640,480,15,24),221.184);
  assert.equal(bandwidthMbps(1,640,480,0,24),0);
  assert.throws(()=>bandwidthMbps(1.5,640,480,15,24));
  assert.throws(()=>bandwidthMbps(1,640,480,15,0));
});
