# Whoopee

A MIDI fart instrument using a reference-fitted contact/resonator model. Half-sine contact forces drive four damped modes; eight voices support MIDI, pitch shifting and turbulence variation.

This is **physical resonator synthesis with a fitted excitation trajectory**, not an autonomous anatomical simulation. The close reference match depends on 420 contact events identified from the recording. No PCM is played at runtime. See [model details and decoding limitations](tools/MODEL.md).

## Build

Requires CMake 3.22+, Git, and a C++17 compiler (Xcode Command Line Tools on macOS or Visual Studio 2022 with C++ on Windows). The first configure downloads JUCE 8.0.6 and its bundled VST3 SDK.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --parallel 2
ctest --test-dir build -C Release --output-on-failure
```

Outputs are under `build/Whoopee_artefacts/Release/`:

- `VST3/Whoopee.vst3` — copy to your DAW's VST3 directory, then rescan plugins.
- `AU/Whoopee.component` on macOS — copy to `~/Library/Audio/Plug-Ins/Components/` for Logic Pro.
- `Standalone/Whoopee.app` on macOS or `Standalone/Whoopee.exe` on Windows — launch to play without a DAW.

On macOS, the user VST3 directory is `~/Library/Audio/Plug-Ins/VST3/`. On Windows, the standard directory is `C:\Program Files\Common Files\VST3\`. This project does not install files automatically. Logic uses the included Audio Unit build, not VST3.

## Play

Load Whoopee as an instrument on a MIDI track, then play notes or click **LET IT RIP**. MIDI note 60 with Pitch 0 and Rasp 0.55 reproduces the fitted reference trajectory. Velocity controls intensity; note-off releases the sound over 25 ms. Voices also end at the configured duration. The preview button plays a full-length note.

- **Pitch:** -24 to +24 semitones relative to each MIDI note.
- **Duration:** 0.08–3 seconds; spreads or compresses the contact sequence to fill the selected time. Applies to newly triggered notes. Hold MIDI notes to hear the full duration.
- **Rasp:** varies the fitted contact forces with turbulence; 0.55 preserves the fitted forces.
- **Volume:** -48 to 0 dB with smoothing; affects all voices.

Pitch transposes the resonator; Duration determines the overall contact-sequence length independently. Pitch, duration, rasp, and volume support host automation and session recall. MIDI all-notes-off/all-sound-off silences all voices. Output is mono-compatible stereo with a safety clamp.

## DSP checks without JUCE

```sh
cmake -S . -B build/dsp -DWHOOPEE_BUILD_PLUGIN=OFF
cmake --build build/dsp
ctest --test-dir build/dsp --output-on-failure
```

CI builds VST3, standalone, and (on macOS) Audio Unit targets on macOS and Windows, runs the DSP checks, and uploads the binaries. DAW scanning, playback, and session recall still need a manual smoke test in your host.

## License

Original project source is covered by the Apache-2.0 license in `LICENSE`. JUCE is a separate dependency with its own AGPLv3/commercial licensing terms; choose the appropriate JUCE license before distributing binaries. See [JUCE licensing](https://juce.com/legal/juce-8-licence/).

This repository replaces the former NuCube implementation. Its previous source remains available in Git history.

## Reference calibration

See [the reproducible identification and verification workflow](tools/MODEL.md). The source WAV is login-gated, so the available MP3 is decoded to floating-point PCM without additional quantization. Verification compares native-rate generated WAVs directly, including waveform error and short-time structure, rather than only matching broad frequency bands.
