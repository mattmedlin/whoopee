import { SlashCommandBuilder } from 'discord.js';
import { presets } from './presets.mjs';

export const commands = [
  new SlashCommandBuilder().setName('fart').setDescription('Play Whoopee in your voice channel').setDMPermission(false)
    .addStringOption(o => o.setName('preset').setDescription('Pick your flavor of questionable acoustics')
      .addChoices(...presets.map(p => ({ name: p.name, value: p.id }))))
    .addNumberOption(o => o.setName('pitch').setDescription('Override pitch in semitones').setMinValue(-24).setMaxValue(24))
    .addNumberOption(o => o.setName('duration').setDescription('Override duration in seconds').setMinValue(0.08).setMaxValue(3))
    .addNumberOption(o => o.setName('rasp').setDescription('Override rasp: smooth to gritty').setMinValue(0).setMaxValue(1)),
  new SlashCommandBuilder().setName('whoopee-leave').setDescription('Disconnect Whoopee from your voice channel').setDMPermission(false),
].map(command => command.toJSON());
