# Whoopee Discord bot 💨

Play the same reference-fitted physical model as the Whoopee instrument in a Discord voice channel. Self-hosted; your computer or server must stay running. No sample playback, FFmpeg, DAW, or paid hosting required.

## Commands

- `/fart` — join your voice channel and let it rip.
- `/fart pitch:-12 duration:2 rasp:0.9` — customize the sound.
- `/whoopee-leave` — disconnect from your voice channel.

Pitch: −24…24 semitones. Duration: 0.08…3 seconds. Rasp: 0…1. Defaults match the app: 0, 0.8, 0.55, with output at −9 dB. One sound plays at a time per server. The bot leaves after 60 seconds idle, cannot be pulled away by someone in another channel, and uses private command replies. Regular voice channels only; Stage channels are not supported.

## 1. Build the sound engine

Install **Node.js 22.12 or newer**, CMake 3.22+, and a C++17 compiler (Xcode Command Line Tools on Mac, Visual Studio C++ on Windows, GCC/Clang on Linux). From the repository root:

```sh
cmake -S . -B build-bot -DWHOOPEE_BUILD_PLUGIN=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-bot --config Release --parallel 2
cd discord-bot
npm ci
```

This build does not download JUCE or build the desktop plugins. On Windows the default renderer path assumes Visual Studio's `build-bot/Release/whoopee_render.exe`. For other generators, set `WHOOPEE_RENDERER` to the absolute executable path.

## 2. Create and invite your bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), create an application named **Whoopee**, and open its **Bot** page.
2. Generate/reset its bot token and keep it private. No privileged gateway intents are needed; leave Message Content, Server Members, and Presence intents off.
3. Copy the **Application ID** from General Information.
4. Under **OAuth2 → URL Generator**, select `bot` and `applications.commands`. Select only **View Channels**, **Connect**, and **Speak** bot permissions. Open the generated URL and install into a server you manage.

Global commands are available in every server that installs the bot. Users must be in a voice channel where the bot has permission to connect and speak. Channel overrides may need adjustment even after installation.

## 3. Configure and run

Copy `.env.example` to `.env` inside `discord-bot`, then fill in:

```dotenv
DISCORD_TOKEN=your_private_bot_token
DISCORD_CLIENT_ID=your_application_id
```

`.env` is ignored by Git. Never put a token in source code, screenshots, or issues. If exposed, reset it in the Developer Portal.

```sh
npm run register
npm start
```

Registration publishes `/fart` and `/whoopee-leave` globally. Repeat registration only when commands change. Discord may take a little time to refresh the command list; reopen Discord if needed. No server ID is required. Join voice, type `/fart` in a text channel, and enjoy. Stop the process with Ctrl+C. To use environment variables supplied by a host instead of a file, run `node src/register.mjs` and `node src/index.mjs` directly.

## Checks and troubleshooting

```sh
npm test
```

Tests require the renderer built in step 1. They check control validation, duration, audible stereo output, pitch/rasp changes, and Opus encoding without contacting Discord. Real voice playback still needs a configured bot and a live server.

- **Startup failed:** check `.env`, Node version, and the renderer executable path.
- **Commands missing:** confirm registration used the right application ID and the invite included `applications.commands`.
- **No audio:** check channel permissions, server mute, and the bot's per-user volume. The hosting network must allow Discord voice UDP traffic.
- **Another channel / one rip at a time:** wait for playback or idle disconnect, or use `/whoopee-leave` while in the bot's channel.

The pinned [Discord voice library](https://discord.js.org/docs/packages/voice/0.19.2) includes DAVE support for encrypted voice. `opusscript` encodes the renderer's 48 kHz stereo PCM, so FFmpeg is unnecessary. The bot does not record voice or request message content.
