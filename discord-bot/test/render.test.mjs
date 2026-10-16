import test from 'node:test';
import assert from 'node:assert/strict';
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';
import { Readable } from 'node:stream';
import { parameters, render, renderer } from '../src/render.mjs';

test('reject invalid controls before starting a process', () => {
  for (const options of [{ pitch: NaN }, { pitch: 25 }, { duration: 0 }, { duration: Infinity },
    { rasp: -1 }, { rasp: '1;echo unsafe' }]) assert.throws(() => parameters(options));
  assert.deepEqual(parameters(), ['0', '0.8', '0.55']);
});

test('native renderer rejects malformed and out-of-range input', async () => {
  for (const args of [['nan', '.8', '.55'], ['0', '4', '.5'], ['0x', '.8', '.5'], ['0', '.8', '2']]) {
    await assert.rejects(promisify(execFile)(renderer, args), error => error.code === 2 && !error.stdout.length);
  }
});

test('renders audible stereo PCM with working duration, pitch, and rasp', async () => {
  const normal = await render();
  const long = await render({ duration: 3 });
  assert.equal(normal.length, 48000 * 0.8 * 4);
  assert.equal(long.length, 48000 * 3 * 4);
  let energy = 0;
  for (let i = 0; i < normal.length; i += 4) {
    assert.equal(normal.readInt16LE(i), normal.readInt16LE(i + 2));
    energy += normal.readInt16LE(i) ** 2;
  }
  assert.ok(energy / (normal.length / 4) > 1000);
  assert.notDeepEqual(normal, await render({ pitch: 12 }));
  assert.notDeepEqual(normal, await render({ rasp: 0 }));
  assert.notDeepEqual(normal, await render({ rasp: 1 }));
});

test('PCM can be encoded to Discord Opus packets', async () => {
  const { default: OpusScript } = await import('opusscript');
  const encoder = new OpusScript(48000, 2, OpusScript.Application.AUDIO);
  try {
    const pcm = await render();
    const packet = encoder.encode(pcm.subarray(0, 960 * 4), 960);
    assert.ok(packet.length > 0);
  } finally { encoder.delete(); }
});

test('Discord voice pipeline consumes PCM without FFmpeg', async () => {
  const { createAudioResource, StreamType } = await import('@discordjs/voice');
  const resource = createAudioResource(Readable.from([await render()]), { inputType: StreamType.Raw });
  let packets = 0;
  for await (const packet of resource.playStream) { assert.ok(packet.length); packets++; }
  assert.ok(packets >= 40);
});

test('slash commands serialize with server-only controls', async () => {
  const { commands } = await import('../src/commands.mjs');
  assert.deepEqual(commands.map(command => command.name), ['fart', 'whoopee-leave']);
  assert.equal(commands[0].dm_permission, false);
  assert.deepEqual(commands[0].options.filter(option => option.name !== 'preset').map(option => [option.min_value, option.max_value]), [[-24, 24], [0.08, 3], [0, 1]]);
});


test('presets render audible audio and explicit zero overrides are preserved', async () => {
  const { presets, soundOptions } = await import('../src/presets.mjs');
  assert.deepEqual(soundOptions(null), { pitch: 0, duration: 0.8, rasp: 0.55 });
  assert.deepEqual(soundOptions('fog-horn', { pitch: 0, rasp: 0 }), { pitch: 0, duration: 3, rasp: 0 });
  assert.throws(() => soundOptions('missing'));
  const { commands } = await import('../src/commands.mjs');
  assert.deepEqual(commands[0].options[0].choices.map(c => c.value), presets.map(p => p.id));
  for (const preset of presets) {
    const pcm = await render(soundOptions(preset.id));
    assert.equal(pcm.length, Math.round(48000 * preset.duration) * 4);
    let energy = 0;
    for (let i = 0; i < pcm.length; i += 4) energy += pcm.readInt16LE(i) ** 2;
    assert.ok(energy / (pcm.length / 4) > 100, preset.name);
  }
});
