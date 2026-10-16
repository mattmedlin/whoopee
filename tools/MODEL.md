# Reference-fitted contact/resonator model

The earlier self-oscillating valve did not match the reference. This replacement is an **identified modal physical model with fitted excitation**, not an anatomical simulation or an independently self-oscillating valve. Its 420 contact-force events encode reference-specific timing, width and signed force. That fitted trajectory is essential to its close match; it would be misleading to attribute the match solely to discovering anatomical constants.

The runtime synthesizes half-sine contact forces, excites a stable eighth-order recurrence (four damped modes), and differentiates the force for acoustic radiation. It does not load PCM, use a recorded wavetable, or decode the MP3. Nevertheless, the event trajectory is a parametric representation fitted to this particular recording, not a general physiological prediction.

## Decoding

The accessible source is the high-quality MP3 preview of Breviceps sound 445998. The original 44.1 kHz / 16-bit stereo WAV requires Freesound login and was not obtained. SoundFile/libsndfile decodes the MP3 directly to float64 at its native sample rate. No gain normalization, lossy re-encoding, or 16-bit quantization is used during fitting. Float64 does not restore information discarded by MP3. The two channels are effectively identical and are averaged.

The resonator identification runs at 8 kHz after anti-aliased polyphase resampling. The runtime uses a 32-tap, 256-phase windowed-sinc interpolator, with four anti-alias cutoff banks for upward transposition. Verification compares the generated output against the original native-rate decoded signal, including frequencies excluded by the reduced-rate model. This prevents the reduced-rate analysis from hiding the remaining error.

## Reproduce

Install NumPy, SciPy and SoundFile in a development environment, then run from the repository root:

```sh
python3 tools/calibrate.py Assets/fart-breviceps.mp3 --output build/modal-fit
python3 tools/export_model.py build/modal-fit/events.json
cmake --build build --config Release --parallel 4
python3 tools/verify_reference.py --renderer build/model_render_raw
```

For multi-configuration generators use `build/Release/model_render_raw.exe` on Windows. `tools/calibration-result.json` contains the fitted identification data used for the checked-in header.

Verification requires correlation above 0.98 and residual SNR above 14.5 dB at 44.1, 48 and 96 kHz. It does not align the signals, fit their gain, or optimize away polarity differences. Listen to the generated comparison as well: these thresholds verify reconstruction fidelity, not an independent perceptual judgment.
