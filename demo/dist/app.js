import { packFrame, unpackFrame, statistics, settingsFromValues, frameRates, bandwidthMbps } from './metrics.js';
const $ = id => document.getElementById(id);
const video = $('capture-video'), canvas = $('camera-output'), output = canvas.getContext('2d');
const captureCanvas = document.createElement('canvas'), captureContext = captureCanvas.getContext('2d');
let ws, camera, timer, clock, running = false, starting = false, targetFPS = 2, lastProfile = 'idle';
let generation = 0;
let settings = settingsFromValues({ idle_fps: 2, active_fps: 15, hold_seconds: 1 });
let startedAt = 0, frameId = 0, skips = 0, windowFrames = [], lastFrame = null, lastFrameAt = 0, displayChain = Promise.resolve();

function message(text, error = false) { $('notice').textContent = text; $('notice').className = error ? 'error' : ''; }
function number(value, digits = 0) { return Number.isFinite(value) ? value.toFixed(digits) : '—'; }
function readSettings() { return settingsFromValues({ idle_fps: Number($('idle-fps').value), active_fps: Number($('active-fps').value), hold_seconds: Number($('hold-seconds').value) }); }
function updateBandwidth() {
  const width = running && video.videoWidth ? Math.min(640, video.videoWidth) : 640;
  const height = running && video.videoWidth ? Math.round(width * video.videoHeight / video.videoWidth) : 480;
  const fps = running ? targetFPS : settings.idle_fps;
  const cameras = Number($('camera-count').value), bpp = Number($('bits-per-pixel').value);
  try {
    const mbps = bandwidthMbps(cameras, width, height, fps, bpp);
    $('bandwidth').innerHTML = `${number(mbps, 2)} <small>Mbps</small>`;
    $('bandwidth-detail').textContent = `${running ? 'Target' : 'Idle preview'}: ${cameras} × ${width} × ${height} × ${fps} × ${bpp} bits/s`;
    const actualFPS = running ? frameRates(windowFrames, startedAt, performance.now()).fps : 0;
    $('bandwidth-actual').textContent = running ? `At actual displayed FPS: ${number(bandwidthMbps(cameras, width, height, actualFPS, bpp), 2)} Mbps` : `Person-present preview: ${number(bandwidthMbps(cameras, width, height, settings.active_fps, bpp), 2)} Mbps · camera off`;
    $('bandwidth-error').textContent = '';
  } catch (error) {
    $('bandwidth').textContent = '—'; $('bandwidth-detail').textContent = ''; $('bandwidth-actual').textContent = ''; $('bandwidth-error').textContent = error.message;
  }
}
function setCaptureRate(fps) {
  const changed = targetFPS !== fps;
  targetFPS = fps; $('rate-badge').textContent = `${fps} FPS target`;
  updateBandwidth();
  if (running && (changed || !timer)) {
    clearInterval(timer); timer = setInterval(captureFrame, 1000 / fps);
  }
}
function resetDisplay() {
  windowFrames = []; lastFrame = null; lastFrameAt = 0; lastProfile = 'idle';
  canvas.width = 640; canvas.height = 480;
  $('camera-empty').hidden = false; $('person-status').textContent = 'CHECKING FOR PERSON';
  $('person-status').classList.remove('active'); $('detection-detail').textContent = 'Waiting for first detection';
  for (const id of ['actual-fps', 'latency', 'drops']) $(id).textContent = '—';
  $('hardware').textContent = '— / —';
}
function connect() {
  const endpoint = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`;
  ws = new WebSocket(endpoint); const socket = ws; socket.binaryType = 'arraybuffer';
  return new Promise((resolve, reject) => {
    let configured = false;
    const timeout = setTimeout(() => { socket.close(); reject(new Error('YOLOv8 did not respond. Start the local gateway with start.ps1.')); }, 10000);
    socket.addEventListener('message', event => {
      if (socket !== ws) return;
      if (typeof event.data === 'string') {
        const data = JSON.parse(event.data);
        if (data.type === 'ready') {
          $('model-info').textContent = `YOLOv8n · person only · ${data.device === 'cpu' ? 'CPU' : 'CUDA'}`;
          socket.send(JSON.stringify({ type: 'configure', settings }));
        } else if (data.type === 'configured') {
          settings = data.settings;
          if (!configured) { configured = true; clearTimeout(timeout); resolve(); }
          else { setCaptureRate(lastProfile === 'active' ? settings.active_fps : settings.idle_fps); message('Settings applied. FPS will change automatically with person detection.'); }
        } else if (data.type === 'error') { message(data.message, true); if (!configured) reject(new Error(data.message)); }
      } else {
        const now = performance.now();
        displayChain = displayChain.then(() => displayFrame(event.data, now, socket)).catch(error => { message(error.message, true); });
      }
    });
    socket.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('Cannot reach the local YOLOv8 gateway. Run start.ps1 and open http://127.0.0.1:8765.')); });
    socket.addEventListener('close', event => {
      clearTimeout(timeout); reject(new Error(event.reason || 'Gateway connection closed.'));
      if (socket === ws && running) { stop(); message(event.reason || 'Gateway disconnected. Start the camera again to reconnect.', true); }
    });
  });
}

async function start() {
  if (running || starting) return;
  const attempt = ++generation;
  starting = true; $('start').disabled = true; $('start').textContent = 'Starting…'; $('stop').disabled = false;
  try {
    settings = readSettings();
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Use localhost or HTTPS in a browser with camera support.');
    await connect();
    if (attempt !== generation) return;
    message('Allow camera access to start person detection.');
    // Camera permission is requested exclusively by this explicit Start action.
    const openedCamera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } }, audio: false });
    if (attempt !== generation) { openedCamera.getTracks().forEach(track => track.stop()); return; }
    camera = openedCamera;
    video.srcObject = camera; await video.play();
    if (attempt !== generation) return;
    for (const track of camera.getVideoTracks()) track.addEventListener('ended', () => { if (running) { stop(); message('Camera disconnected. Reconnect it and start again.', true); } });
    resetDisplay(); startedAt = performance.now(); frameId = skips = 0;
    running = true; targetFPS = settings.idle_fps; setCaptureRate(targetFPS); captureFrame();
    $('stop').disabled = false; $('connection').textContent = 'Camera on · local YOLOv8';
    clock = setInterval(updateMetrics, 250);
    message('Camera running. Move into view to raise FPS; leave the frame to lower it.');
  } catch (error) {
    if (attempt !== generation) return;
    stop();
    message(error.name === 'NotAllowedError' ? 'Camera access was denied. Allow camera access for this page, then click Start camera.' : error.name === 'NotFoundError' ? 'No camera was found. Connect or enable your laptop camera.' : error.name === 'NotReadableError' ? 'Camera is busy or unavailable. Close other apps using the camera, then try again.' : error.message, true);
  } finally { if (attempt === generation) { starting = false; $('start').disabled = running; $('start').textContent = 'Start camera'; } }
}
function stop() {
  generation++; starting = false; running = false; clearInterval(timer); clearInterval(clock); timer = clock = null;
  if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
  if (camera) { camera.getTracks().forEach(track => track.stop()); camera = null; }
  video.pause(); video.srcObject = null;
  // Remove the camera image when stopped instead of leaving a private frame visible.
  output.clearRect(0, 0, canvas.width, canvas.height); $('camera-empty').hidden = false;
  $('person-status').textContent = 'CAMERA OFF'; $('person-status').classList.remove('active'); $('rate-badge').textContent = '— FPS';
  $('detection-detail').textContent = 'Camera stopped'; $('connection').textContent = 'Local YOLOv8 · camera off';
  $('start').disabled = false; $('start').textContent = 'Start camera'; $('stop').disabled = true;
  updateBandwidth();
}
function captureFrame() {
  if (!running || ws?.readyState !== WebSocket.OPEN || video.readyState < 2) return;
  if (ws.bufferedAmount > 128000) { skips++; return; }
  const captureMS = performance.now();
  try {
    const width = Math.min(640, video.videoWidth);
    captureCanvas.width = width; captureCanvas.height = Math.round(width * video.videoHeight / video.videoWidth);
    captureContext.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    const data = captureCanvas.toDataURL('image/jpeg', .7), raw = atob(data.slice(data.indexOf(',') + 1));
    ws.send(packFrame({ id: ++frameId, capture_ms: captureMS }, Uint8Array.from(raw, c => c.charCodeAt(0))));
  } catch (error) { skips++; message(`Camera frame could not be sent: ${error.message}`, true); }
}
async function displayFrame(buffer, receivedAt, socket) {
  if (!running || socket !== ws) return;
  const { metadata, jpeg } = unpackFrame(buffer);
  lastProfile = metadata.profile; setCaptureRate(metadata.target_fps);
  const bitmap = await createImageBitmap(new Blob([jpeg], { type: 'image/jpeg' }));
  if (!running || socket !== ws) { bitmap.close(); return; }
  canvas.width = bitmap.width; canvas.height = bitmap.height; output.drawImage(bitmap, 0, 0); bitmap.close();
  lastFrameAt = performance.now(); lastFrame = metadata;
  windowFrames.push({ time: lastFrameAt, latency: lastFrameAt - metadata.capture_ms });
  $('camera-empty').hidden = true;
  $('person-status').textContent = metadata.detected ? 'PERSON DETECTED' : metadata.profile === 'active' ? 'HOLDING HIGH FPS' : 'NOBODY DETECTED';
  $('person-status').classList.toggle('active', metadata.profile === 'active');
  $('detection-detail').textContent = metadata.detected ? `${metadata.boxes.length} person${metadata.boxes.length === 1 ? '' : 's'} detected` : metadata.profile === 'active' ? `Waiting ${settings.hold_seconds}s before slowing down` : 'Watching at low FPS for someone to return';
  $('camera-detail').textContent = `${metadata.width} × ${metadata.height} · JPEG ${metadata.quality}`;
  updateMetrics();
}
function updateMetrics() {
  if (!running) return;
  const now = performance.now(); windowFrames = windowFrames.filter(frame => frame.time > now - 3000);
  const rates = frameRates(windowFrames, startedAt, now), latency = statistics(windowFrames.map(frame => frame.latency));
  $('actual-fps').innerHTML = `${number(rates.fps, 1)} <small>fps</small>`;
  $('fps-detail').textContent = `Target ${targetFPS} FPS · actual over last 3 seconds`;
  $('latency').innerHTML = `${number(latency.median)} <small>ms</small>`;
  $('latency-detail').textContent = `Median · p95 ${number(latency.p95)} ms`;
  updateBandwidth();
  if (lastFrame) {
    const drops = lastFrame.counters.dropped + skips;
    $('drops').textContent = String(drops); $('drop-detail').textContent = `${lastFrame.counters.dropped} queue drops · ${skips} capture skips`;
    const hardware = lastFrame.hardware;
    $('hardware').textContent = `${number(hardware.cpu_percent)}% / ${Number.isFinite(hardware.gpu_percent) ? `${number(hardware.gpu_percent)}%` : 'N/A'}`;
    $('hardware-detail').textContent = `CPU / GPU 0 · inference on ${lastFrame.device === 'cpu' ? 'CPU' : 'CUDA'}`;
    $('session-info').textContent = `${lastFrame.counters.delivered} frames received · person checks continue at idle FPS`;
    if (now - lastFrameAt > 4000) {
      $('person-status').textContent = 'WAITING FOR INFERENCE'; $('person-status').classList.remove('active');
      $('detection-detail').textContent = 'No recent result from the gateway';
      $('hardware-detail').textContent = 'Last hardware reading · waiting for gateway';
    }
  }
}
$('start').addEventListener('click', start);
$('stop').addEventListener('click', () => { stop(); message('Camera stopped. Click Start camera to run again.'); });
$('settings-form').addEventListener('submit', event => {
  event.preventDefault();
  try { const next = readSettings(); if (running && ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'configure', settings: next })); else { settings = next; updateBandwidth(); message('FPS settings saved for the next camera session.'); } }
  catch (error) { message(error.message, true); }
});
window.addEventListener('pagehide', stop);
for (const id of ['camera-count', 'bits-per-pixel']) $(id).addEventListener('input', updateBandwidth);
updateBandwidth();
if (document.modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const tool = { name: 'read_camera_metrics', title: 'Read camera metrics', description: 'Read measured person detection and adaptive FPS. Does not start the camera.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true }, execute(input) { if (Object.keys(input || {}).length) throw new Error('No arguments accepted'); return { running, target_fps: running ? targetFPS : null, person_detected: running ? lastFrame?.detected ?? null : null, displayed_fps: running ? frameRates(windowFrames, startedAt, performance.now()).fps : null, latest: running ? { inference_ms: lastFrame?.inference_ms ?? null, profile: lastFrame?.profile ?? null } : null }; } };
  Promise.resolve(document.modelContext.registerTool(tool, { signal: lifecycle.signal })).catch(() => {});
  window.addEventListener('pagehide', () => lifecycle.abort(), { once: true });
}
