from pathlib import Path
import subprocess,json,os
r=Path('videos/backing-intro');records=[]
for name in ['backing-intro','backing-intro-nobgm']:
 backup=r/f'out/{name}-render.mp4'
 if backup.exists():
  raise FileExistsError(f'Render backup already exists: {backup}')
for name in ['backing-intro','backing-intro-nobgm']:
 original=r/f'out/{name}.mp4';target=r/f'out/{name}-final.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(original),'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af','atrim=duration=60','-t','60','-movflags','+faststart',str(target)],check=True)
 original.replace(r/f'out/{name}-render.mp4');target.replace(original)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,duration,nb_frames,width,height,r_frame_rate','-of','json',str(original)]))
 records.append({'file':name+'.mp4',**probe});print(name,probe['format'])
# Use one canonical H.264 stream for both versions. Independent lossy encodes
# can differ at the pixel level even with the same deterministic composition.
matched=r/'out/backing-intro-nobgm-matched.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(r/'out/backing-intro.mp4'),'-i',str(r/'out/backing-intro-nobgm.mp4'),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(matched)],check=True)
matched.replace(r/'out/backing-intro-nobgm.mp4')
records[1]['format']['size']=str((r/'out/backing-intro-nobgm.mp4').stat().st_size)
(r/'analysis/delivery-media.json').write_text(json.dumps(records,indent=2))
# Record the exact signed beat error, including measured output delay.
b=json.loads((r/'analysis/beat_data.json').read_text());cuts=[180,416,667,903,1197,1464,1626]
errs=[]
for f in cuts:
 beat=min(b['beats'],key=lambda t:abs(t-f/30));errs.append({'cut_frame':f,'source_beat_seconds':beat,'rendered_beat_frame':beat*30+1.27,'error_frames':f-(beat*30+1.27)})
(r/'analysis/final-beat-errors.json').write_text(json.dumps(errs,indent=2));print('Max beat error',max(abs(x['error_frames']) for x in errs))
