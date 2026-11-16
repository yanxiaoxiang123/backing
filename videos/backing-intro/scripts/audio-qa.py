import subprocess,numpy as np,json
from scipy.signal import correlate
from pathlib import Path
r=Path('videos/backing-intro')
def samples(p):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar','48000','-f','f32le','-']),dtype=np.float32)
y=samples(r/'out/backing-intro-nobgm.mp4');report=[]
for src,start,target in [('fs-812748.mp3',27,33),('fs-534103.mp3',488,490),('fs-812748.mp3',1669,1675)]:
 x=samples(r/'public/audio/sfx'/src);low=int(max(0,start/30-.2)*48000);high=int((start/30+len(x)/48000+.2)*48000);seg=y[low:high]
 c=correlate(seg,x,mode='valid',method='fft');pos=low+int(np.argmax(c));peak=.155 if '812748' in src else .035
 actual=(pos/48000+peak)*30
 report.append({'source':src,'target_frame':target,'measured_peak_frame':actual,'residual_frames':actual-target,'observed_start_frame':pos/1600})
print(json.dumps(report,indent=2));(r/'analysis/final-audio-sync.json').write_text(json.dumps(report,indent=2))
for name in ['backing-intro','backing-intro-nobgm']:
 proc=subprocess.run(['ffmpeg','-hide_banner','-i',str(r/f'out/{name}.mp4'),'-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True)
 (r/f'analysis/{name}-loudness.txt').write_text(proc.stderr,encoding='utf-8');print(name,proc.stderr[proc.stderr.rfind('{'):])
