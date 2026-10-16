#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
artifacts="build/Whoopee_artefacts/Release"
staging="build/release-stage"
output="build/release"
mkdir -p "$staging/standalone/Licenses" "$staging/plugins/Licenses" "$output"
for package in standalone plugins; do
    cp LICENSE "$staging/$package/Licenses/Whoopee-Apache-2.0.txt"
    cp LICENSES/* "$staging/$package/Licenses/"
    cat > "$staging/$package/READ-ME.txt" <<'TEXT'
WHOOPEE — a MIDI-playable fart instrument

Requires Apple Silicon (M1 or newer), macOS 14 or later.
Standalone: drag Whoopee.app to Applications, then click LET IT RIP.
Options selects your audio output and MIDI inputs.
Plugins: copy Whoopee.component to ~/Library/Audio/Plug-Ins/Components/
and Whoopee.vst3 to ~/Library/Audio/Plug-Ins/VST3/. Restart/rescan your DAW.

This is an ad-hoc signed development release, not Apple-notarized.
macOS first-launch help: https://support.apple.com/102445

Whoopee source: Apache-2.0. Combined binaries contain AGPLv3 JUCE.
Complete corresponding source, including dependency notices:
https://github.com/mattmedlin/whoopee/releases/download/v1.0.1/Whoopee-Source.zip
Project and instructions: https://github.com/mattmedlin/whoopee
TEXT
done
ditto "$artifacts/Standalone/Whoopee.app" "$staging/standalone/Whoopee.app"
ditto "$artifacts/AU/Whoopee.component" "$staging/plugins/Whoopee.component"
ditto "$artifacts/VST3/Whoopee.vst3" "$staging/plugins/Whoopee.vst3"
for bundle in "$staging/standalone/Whoopee.app" "$staging/plugins/Whoopee.component" "$staging/plugins/Whoopee.vst3"; do
    codesign --force --sign - "$bundle"
    codesign --verify --deep --strict "$bundle"
done
ditto -c -k --sequesterRsrc "$staging/standalone" "$output/Whoopee-Standalone-macOS-Apple-Silicon.zip"
ditto -c -k --sequesterRsrc "$staging/plugins" "$output/Whoopee-Plugins-macOS-Apple-Silicon.zip"
python3 - <<'PY'
import os,subprocess,zipfile
from pathlib import Path
root=Path.cwd()
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
with zipfile.ZipFile('build/release/Whoopee-Source.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for rel in sorted(set(paths)):
        p=root/rel
        if rel and p.is_file(): z.write(p,'Whoopee-Source/'+rel)
    vendor=root/'build/_deps/juce-src'
    for directory,folders,files in os.walk(vendor):
        folders[:]=[f for f in folders if f!='.git']
        for name in files:
            p=Path(directory)/name
            if name!='.git': z.write(p,'Whoopee-Source/vendor/JUCE/'+str(p.relative_to(vendor)))
PY
