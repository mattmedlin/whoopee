"""Compare actual generated PCM with the available MP3 reference.
Requires NumPy, SciPy, SoundFile. No alignment search or gain fitting is used
for raw-renderer metrics: the test must reproduce onset, polarity and level.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal

parser=argparse.ArgumentParser()
parser.add_argument('--renderer', required=True)
parser.add_argument('--reference', default='Assets/fart-breviceps.mp3')
parser.add_argument('--output', default='build/reference-verification')
args=parser.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
reference,rate=sf.read(args.reference,dtype='float64',always_2d=True)
assert rate==44100
reference=reference.mean(axis=1)
report={'source_sha256':hashlib.sha256(Path(args.reference).read_bytes()).hexdigest(),
        'source':'Lossy MP3 preview; original WAV requires Freesound login',
        'decode':'libsndfile via SoundFile, float64, native 44100 Hz, no normalization',
        'model':'Four-mode identified resonator with 420 fitted contact-force events',
        'tests':[]}
for sample_rate in [44100,48000,96000]:
    raw=subprocess.check_output([str(Path(args.renderer).resolve()),str(sample_rate)])
    rendered=np.frombuffer(raw,dtype='<f4').astype(np.float64)
    if sample_rate!=rate:
        g=np.gcd(sample_rate,rate)
        rendered=signal.resample_poly(rendered,rate//g,sample_rate//g)
    rendered=rendered[:len(reference)]
    error=reference-rendered
    snr=float(10*np.log10(np.sum(reference**2)/np.sum(error**2)))
    correlation=float(np.corrcoef(reference,rendered)[0,1])
    report['tests'].append({'sample_rate':sample_rate,'waveform_correlation':correlation,
                            'snr_db':snr,'residual_energy_fraction':float(np.sum(error**2)/np.sum(reference**2))})
    assert np.isfinite(rendered).all() and max(abs(rendered))<1
    assert correlation>0.98 and snr>14.5, report['tests'][-1]
    if sample_rate==rate:
        sf.write(out/'reference.wav',reference,rate,subtype='PCM_24')
        sf.write(out/'model.wav',rendered,rate,subtype='PCM_24')
        # Identical gain, no hidden level/phase optimization.
        comparison=np.concatenate([reference,np.zeros(rate//2),rendered,np.zeros(rate//2),reference,np.zeros(rate//2),rendered])
        sf.write(out/'reference-then-model.wav',comparison,rate,subtype='PCM_24')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
