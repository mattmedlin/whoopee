import { REST, Routes } from 'discord.js';
import { commands } from './commands.mjs';

const { DISCORD_TOKEN: token, DISCORD_CLIENT_ID: client, DISCORD_GUILD_ID: guild } = process.env;
if (!token || !/^\d+$/.test(client || '') || !/^\d+$/.test(guild || '')) {
  console.error('Set DISCORD_TOKEN, DISCORD_CLIENT_ID, and DISCORD_GUILD_ID in .env.');
  process.exit(1);
}
try {
  // Upsert only our named commands; preserve other commands on the application.
  const rest = new REST({ version: '10' }).setToken(token);
  for (const command of commands) await rest.post(Routes.applicationGuildCommands(client, guild), { body: command });
  console.log('Registered /fart and /whoopee-leave in your server.');
} catch {
  console.error('Registration failed. Check the token, application/server IDs, and bot installation.');
  process.exitCode = 1;
}
