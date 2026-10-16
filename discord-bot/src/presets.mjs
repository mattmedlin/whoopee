export const presets = [
  { id: 'fog-horn', name: 'The Fog Horn — long & deep', pitch: -18, duration: 3, rasp: 0.65 },
  { id: 'sneak-attack', name: 'Sneak Attack — short & quick', pitch: 2, duration: 0.18, rasp: 0.55 },
  { id: 'rumble-seat', name: 'Rumble Seat — low & raspy', pitch: -12, duration: 1.8, rasp: 0.95 },
  { id: 'squeaky-cheeks', name: 'Squeaky Cheeks — tiny & high', pitch: 19, duration: 0.25, rasp: 0.4 },
  { id: 'lawn-mower', name: 'The Lawn Mower — long & gritty', pitch: -5, duration: 2.6, rasp: 1 },
  { id: 'velvet-toot', name: 'Velvet Toot — soft & mellow', pitch: -7, duration: 0.65, rasp: 0.08 },
  { id: 'whoops', name: 'Whoops — one quick rip', pitch: -3, duration: 0.35, rasp: 0.85 },
  { id: 'board-meeting', name: 'The Board Meeting — uncomfortably long', pitch: -9, duration: 3, rasp: 0.8 },
];

export function soundOptions(presetId, overrides = {}) {
  const preset = presetId == null ? null : presets.find(p => p.id === presetId);
  if (presetId != null && !preset) throw new Error('Unknown preset.');
  return {
    pitch: overrides.pitch ?? preset?.pitch ?? 0,
    duration: overrides.duration ?? preset?.duration ?? 0.8,
    rasp: overrides.rasp ?? preset?.rasp ?? 0.55,
  };
}
