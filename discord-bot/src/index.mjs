import { access } from 'node:fs/promises';
import { Readable } from 'node:stream';
import { Client, GatewayIntentBits, ChannelType, PermissionFlagsBits, MessageFlags } from 'discord.js';
import { joinVoiceChannel, createAudioPlayer, createAudioResource, entersState,
  AudioPlayerStatus, VoiceConnectionStatus, StreamType } from '@discordjs/voice';
import { render, renderer } from './render.mjs';
import { soundOptions } from './presets.mjs';

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
const sessions = new Map();
const busy = new Set();

function close(guild) {
  const session = sessions.get(guild);
  if (!session) return;
  sessions.delete(guild);
  clearTimeout(session.timer);
  session.player.stop(true);
  if (session.connection.state.status !== VoiceConnectionStatus.Destroyed) session.connection.destroy();
}

function idle(guild, session) {
  clearTimeout(session.timer);
  session.timer = setTimeout(() => close(guild), 60_000);
  session.timer.unref();
}

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand() || !['fart', 'whoopee-leave'].includes(interaction.commandName)) return;
  const guild = interaction.guildId;
  let locked = false;
  try {
    await interaction.deferReply({ flags: MessageFlags.Ephemeral });
    if (!interaction.inGuild()) {
      await interaction.editReply('Use this command in a server voice channel.'); return;
    }
    const member = await interaction.guild.members.fetch(interaction.user.id);
    const channel = member.voice.channel;
    if (!channel || channel.type !== ChannelType.GuildVoice) {
      await interaction.editReply('Join a regular voice channel first.'); return;
    }
    const existing = sessions.get(guild);
    if (existing && existing.channelId !== channel.id) {
      await interaction.editReply('Whoopee is already in another channel. Join that channel or wait for it to disconnect.'); return;
    }
    if (busy.has(guild)) { await interaction.editReply('One rip at a time—try again in a moment.'); return; }
    if (interaction.commandName === 'whoopee-leave') {
      close(guild); await interaction.editReply('Whoopee disconnected.'); return;
    }
    const me = await interaction.guild.members.fetchMe();
    if (!channel.permissionsFor(me)?.has([PermissionFlagsBits.ViewChannel, PermissionFlagsBits.Connect, PermissionFlagsBits.Speak])) {
      await interaction.editReply('I need View Channel, Connect, and Speak permissions in your voice channel.'); return;
    }
    // Recheck after async permission lookup before acquiring the per-server lock.
    if (busy.has(guild)) { await interaction.editReply('One rip at a time—try again in a moment.'); return; }
    busy.add(guild); locked = true;
    const pcm = await render(soundOptions(interaction.options.getString('preset'), {
      pitch: interaction.options.getNumber('pitch'), duration: interaction.options.getNumber('duration'),
      rasp: interaction.options.getNumber('rasp'),
    }));
    let session = sessions.get(guild);
    if (session && session.channelId !== channel.id) {
      await interaction.editReply('Whoopee is now in another channel. Try again there.'); return;
    }
    if (!session) {
      const connection = joinVoiceChannel({ channelId: channel.id, guildId: guild,
        adapterCreator: interaction.guild.voiceAdapterCreator, selfDeaf: true });
      session = { connection, player: createAudioPlayer(), channelId: channel.id };
      sessions.set(guild, session);
      connection.on('error', () => close(guild));
      connection.on(VoiceConnectionStatus.Disconnected, () => close(guild));
      session.player.on('error', () => close(guild));
      connection.subscribe(session.player);
    }
    clearTimeout(session.timer);
    await entersState(session.connection, VoiceConnectionStatus.Ready, 15_000);
    if (member.voice.channelId !== channel.id || me.voice.serverMute) throw new Error('Voice state changed');
    const resource = createAudioResource(Readable.from([pcm]), { inputType: StreamType.Raw });
    session.player.play(resource);
    await entersState(session.player, AudioPlayerStatus.Playing, 5000);
    await interaction.editReply('💨');
    await entersState(session.player, AudioPlayerStatus.Idle, 10_000);
    if (sessions.get(guild) === session) idle(guild, session);
  } catch {
    if (locked) close(guild);
    const content = 'Could not play Whoopee. Check the renderer build, voice permissions, and bot connection.';
    try {
      if (interaction.deferred || interaction.replied) await interaction.editReply(content);
      else await interaction.reply({ content, flags: MessageFlags.Ephemeral });
    } catch { /* Interaction expired or Discord unavailable. */ }
    console.error('A Whoopee command failed (no credentials logged).');
  } finally { if (locked) busy.delete(guild); }
});

client.once('clientReady', () => console.log('Whoopee is ready. Join voice and use /fart.'));
client.on('error', () => console.error('Discord connection error.'));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  for (const guild of sessions.keys()) close(guild);
  client.destroy();
  process.exit(0);
});

try {
  if (!process.env.DISCORD_TOKEN) throw new Error('Missing config');
  await access(renderer);
  await client.login(process.env.DISCORD_TOKEN);
} catch {
  console.error('Startup failed. Build whoopee_render and configure DISCORD_TOKEN in .env.');
  client.destroy();
  process.exitCode = 1;
}
