import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

export const renderer = process.env.WHOOPEE_RENDERER || fileURLToPath(new URL(
  process.platform === 'win32' ? '../../build-bot/Release/whoopee_render.exe' : '../../build-bot/whoopee_render', import.meta.url));

export function parameters({ pitch = 0, duration = 0.8, rasp = 0.55 } = {}) {
  const values = [pitch, duration, rasp];
  const bounds = [[-24, 24], [0.08, 3], [0, 1]];
  if (values.some((value, i) => typeof value !== 'number' || !Number.isFinite(value)
    || value < bounds[i][0] || value > bounds[i][1])) throw new Error('Invalid sound controls.');
  return values.map(String);
}

export async function render(options) {
  const { stdout } = await promisify(execFile)(renderer, parameters(options), {
    encoding: 'buffer', timeout: 5000, maxBuffer: 600_000, windowsHide: true,
  });
  if (!stdout.length || stdout.length % 4) throw new Error('Invalid renderer output.');
  return stdout;
}
