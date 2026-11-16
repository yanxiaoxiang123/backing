import {chromium} from '../../../frontend/node_modules/playwright/index.mjs'
import path from 'node:path'
const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1920,height:1080}})
await p.goto('file:///'+path.resolve('videos/backing-intro/styleframes.html').replaceAll('\\','/'));await p.evaluate(()=>document.fonts.ready)
for(let i=0;i<3;i++){await p.evaluate(i=>scrollTo(0,i*1080),i);await p.screenshot({path:`videos/backing-intro/out/qa/styleframe-${i}.png`})}
await b.close()
