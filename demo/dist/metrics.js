export function statistics(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return { mean: null, median: null, p95: null };
  const center = (sorted.length - 1) / 2;
  return { mean: sorted.reduce((a, b) => a + b, 0) / sorted.length, median: (sorted[Math.floor(center)] + sorted[Math.ceil(center)]) / 2, p95: sorted[Math.max(0, Math.ceil(sorted.length * .95) - 1)] };
}
export function settingsFromValues(values) {
  const settings = { confidence: .35, idle_fps: values.idle_fps, active_fps: values.active_fps, hold_seconds: values.hold_seconds };
  if (!Number.isInteger(settings.idle_fps) || settings.idle_fps < 1 || settings.idle_fps > 10) throw new Error('Idle FPS must be an integer from 1 to 10.');
  if (!Number.isInteger(settings.active_fps) || settings.active_fps < 2 || settings.active_fps > 30) throw new Error('Person-present FPS must be an integer from 2 to 30.');
  if (settings.idle_fps >= settings.active_fps) throw new Error('Idle FPS must be lower than person-present FPS.');
  if (!Number.isFinite(settings.hold_seconds) || settings.hold_seconds < 0 || settings.hold_seconds > 10) throw new Error('Detection hold must be between 0 and 10 seconds.');
  return settings;
}
export function packFrame(metadata, jpeg) {
  const header = new TextEncoder().encode(JSON.stringify(metadata)), packet = new Uint8Array(4 + header.length + jpeg.length);
  new DataView(packet.buffer).setUint32(0, header.length); packet.set(header, 4); packet.set(jpeg, 4 + header.length); return packet;
}
export function unpackFrame(buffer) {
  if (buffer.byteLength < 5) throw new Error('Truncated frame packet.');
  const size = new DataView(buffer).getUint32(0); if (size > 1000000 || size + 4 >= buffer.byteLength) throw new Error('Invalid frame header.');
  return { metadata: JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, size))), jpeg: new Uint8Array(buffer, 4 + size) };
}
export function frameRates(frames, startedAt, now, windowMs = 3000) {
  const count = frames.filter(frame => frame.time > now - windowMs && frame.time <= now).length;
  return { fps: count / Math.max(.1, Math.min(windowMs, now - startedAt) / 1000) };
}
export function bandwidthMbps(cameras, width, height, fps, bitsPerPixel) {
  if (!Number.isInteger(cameras) || cameras < 1 || cameras > 1000) throw new Error('Camera count must be an integer from 1 to 1000.');
  if (!Number.isFinite(bitsPerPixel) || bitsPerPixel <= 0 || bitsPerPixel > 64) throw new Error('Bits per pixel must be greater than 0 and at most 64.');
  if (![width, height].every(value => Number.isInteger(value) && value > 0) || !Number.isFinite(fps) || fps < 0) throw new Error('Invalid frame dimensions or FPS.');
  return cameras * width * height * fps * bitsPerPixel / 1_000_000;
}
