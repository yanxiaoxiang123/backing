import {bundle} from '@remotion/bundler'
import {selectComposition,renderStill} from '@remotion/renderer'
import fs from 'node:fs/promises'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const url=await bundle({entryPoint:path.join(root,'src/index.ts'),publicDir:path.join(root,'public')})
await fs.writeFile(path.join(root,'analysis/bundle-url.txt'),url)
const browserExecutable=path.join(root,'node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe')
const comp=await selectComposition({browserExecutable,serveUrl:url,id:'BackingIntro',inputProps:{bgm:false}})
const frames=process.argv.slice(2).length?process.argv.slice(2).map(Number):[30,120,210,310,455,540,715,825,955,1080,1235,1380,1510,1570,1650,1750]
for(const f of frames){await renderStill({browserExecutable,serveUrl:url,composition:comp,frame:f,output:path.join(root,`out/qa/f${f}.png`),inputProps:{bgm:false},chromiumOptions:{gl:'angle'}});console.log('still',f)}
