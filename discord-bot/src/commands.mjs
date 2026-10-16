import { SlashCommandBuilder } from 'discord.js';

export const commands = [
  new SlashCommandBuilder().setName('fart').setDescription('Play Whoopee in your voice channel').setDMPermission(false)
    .addNumberOption(o => o.setName('pitch').setDescription('Semitones (default 0)').setMinValue(-24).setMaxValue(24))
    .addNumberOption(o => o.setName('duration').setDescription('Seconds (default 0.8)').setMinValue(0.08).setMaxValue(3))
    .addNumberOption(o => o.setName('rasp').setDescription('Smooth to gritty (default 0.55)').setMinValue(0).setMaxValue(1)),
  new SlashCommandBuilder().setName('whoopee-leave').setDescription('Disconnect Whoopee from your voice channel').setDMPermission(false),
].map(command => command.toJSON());
