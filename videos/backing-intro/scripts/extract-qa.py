from pathlib import Path
import subprocess
p=Path('videos/backing-intro/out');qa=p/'qa'
qa.mkdir(parents=True,exist_ok=True)
frames=[30,120,210,310,455,494,540,681,715,825,955,1080,1208,1235,1380,1510,1570,1650,1750,1799]
for frame in frames:
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(p/'backing-intro.mp4'),'-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(qa/f'final-f{frame}.png')],check=True)
from PIL import Image,ImageDraw
out=Image.new('RGB',(1920,5*390),'#eeeeee');d=ImageDraw.Draw(out)
for i,f in enumerate([120,310,494,540,715,825,955,1080,1235,1380,1510,1570,1650,1750,1799]):
 im=Image.open(qa/f'final-f{f}.png');im.thumbnail((640,360));x=i%3*640;y=i//3*390;out.paste(im,(x,y));d.text((x+12,y+364),f'f{f} / {f/30:.2f}s',fill='#222222')
out.save(qa/'contact-final.jpg')
