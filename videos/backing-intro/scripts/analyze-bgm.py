import librosa,numpy as np,json
from pathlib import Path
from scipy.signal import butter,sosfilt,find_peaks
p=Path('videos/backing-intro');y,sr=librosa.load(str(p/'public/audio/bgm.mp3'),sr=22050,duration=65,mono=True)
tempo,bt=librosa.beat.beat_track(y=y,sr=sr,tightness=400,units='time')
i=np.arange(len(bt));(period,t0),*_ =np.linalg.lstsq(np.vstack([i,np.ones_like(i)]).T,bt,rcond=None)
# Preserve measured beat locations for sparse cuts rather than inventing an exact grid.
hits=[]
for kind,lo,hi in [('kick',40,160),('snare',150,3000),('hihat',6000,10000)]:
 filtered=sosfilt(butter(4,[lo,hi],btype='band',fs=sr,output='sos'),y)
 env=librosa.onset.onset_strength(y=filtered,sr=sr,hop_length=256);ts=librosa.times_like(env,sr=sr,hop_length=256)
 inds,_=find_peaks(env,distance=12,prominence=max(.2,float(np.std(env))*.5))
 hits +=[{'t':float(ts[x]),'s':float(env[x]),'k':kind} for x in inds]
res=bt-(t0+i*period)
data={'bpm':float(60/period),'t0':float(t0),'T':float(period),'beats':bt.tolist(),'hits':hits,'residual_max_ms':float(abs(res).max()*1000),'sr':sr,'note':'Content-paced project film; source BGM selected after storyboard. Sparse cuts align to nearest measured beat, no camera pumping.'}
(p/'analysis/beat_data.json').write_text(json.dumps(data,indent=2))
print('BPM',60/period,'phase',t0,'residual max ms',abs(res).max()*1000)
print('cuts',[(t,float(bt[np.argmin(abs(bt-t))])) for t in [6,14,22,30,40,49,54]])
