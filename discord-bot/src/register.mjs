import { REST, Routes } from 'discord.js';
import { commands } from './commands.mjs';

const { DISCORD_TOKEN: token, DISCORD_CLIENT_ID: client } = process.env;
if (!token || !/^\d+$/.test(client || '')) {
  console.error('Set DISCORD_TOKEN, DISCORD_CLIENT_ID in .env.');
  process.exit(1);
}
try {
  // Upsert only our named commands; preserve other commands on the application.
  const rest = new REST({ version: '10' }).setToken(token);
  for (const command of commands) await rest.post(Routes.applicationCommands(client), { body: command });
  console.log('Registered /fart and /whoopee-leave globally.');
} catch {
  console.error('Registration failed. Check the token, application ID, and bot installation.');
  process.exitCode = 1;
}
