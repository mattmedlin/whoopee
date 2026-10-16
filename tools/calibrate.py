import numpy as np, soundfile as sf, json
from scipy import signal,linalg
import argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('reference', help='Original WAV or available MP3 preview')
parser.add_argument('--output',default='build/modal-fit')
args=parser.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
x,rate=sf.read(args.reference, dtype='float64',always_2d=True)
assert rate==44100
x=x.mean(axis=1);x-=x.mean();x=signal.resample_poly(x,80,441);sr=8000;n=len(x)
ac=signal.correlate(x,x,mode='full',method='fft')[n-1:n+8]
a=np.r_[1,linalg.solve_toeplitz(ac[:8],-ac[1:9])]
# A compact passive resonant transfer function identified from the source.
impulse=np.r_[1.,np.zeros(799)];h=signal.lfilter([1,-1],a,impulse)
kernels=[]
for width in [1,2,4,8,16]:
 pulse=np.sin(np.pi*(np.arange(width)+.5)/width);pulse/=pulse.sum()
 k=signal.fftconvolve(h,pulse)[:800];kernels.append(k/np.linalg.norm(k))
res=x.copy();events=[];cols=[]
for j in range(420):
 scores=[]
 for k in kernels:
  corr=signal.correlate(res,k,mode='full',method='fft')[len(k)-1:len(k)-1+n]
  scores.append(corr)
 scores=np.array(scores)
 for i,t in events:scores[:,max(0,t-3):t+4]=0
 ki,t=np.unravel_index(abs(scores).argmax(),scores.shape)
 col=np.zeros(n);count=min(n-t,len(kernels[ki]));col[t:t+count]=kernels[ki][:count]
 cols.append(col);events.append((ki,t));matrix=np.array(cols).T
 weights=linalg.lstsq(matrix,x,lapack_driver='gelsy')[0];res=x-matrix@weights
 if j in [59,119,179,239,299,359,419]:print(j+1,'SNR',10*np.log10(np.sum(x*x)/np.sum(res*res)),flush=True)
for iteration in range(3):
 for j,(ki,t) in enumerate(events):
  target=res+matrix[:,j]*weights[j]
  best=(-1,None)
  for kidx,k in enumerate(kernels):
   for tt in range(max(0,t-16),min(n,t+17),2):
    count=min(n-tt,len(k));ks=k[:count];dot=target[tt:tt+count]@ks;norm=ks@ks
    quality=dot*dot/norm
    if quality>best[0]:best=(quality,(kidx,tt,dot/norm))
  ki,t,w=best[1];events[j]=(ki,t);weights[j]=w;matrix[:,j]=0
  count=min(n-t,len(kernels[ki]));matrix[t:t+count,j]=kernels[ki][:count]
  res=target-matrix[:,j]*w
 weights=linalg.lstsq(matrix,x,lapack_driver='gelsy')[0];res=x-matrix@weights
 print('refine',iteration,'SNR',10*np.log10(np.sum(x*x)/np.sum(res*res)),flush=True)
sf.write(str(out/'render.wav') ,signal.resample_poly(x-res,441,80),44100,subtype='FLOAT')
json.dump({'a':a.tolist(),'events':[[int(i),int(t),float(w)] for (i,t),w in zip(events,weights)],'sr':sr,'kernel_norms':[float(np.linalg.norm(signal.fftconvolve(h,np.sin(np.pi*(np.arange(width)+.5)/width)/np.sin(np.pi*(np.arange(width)+.5)/width).sum())[:800])) for width in [1,2,4,8,16]]},open(out/'events.json','w'),indent=2)
