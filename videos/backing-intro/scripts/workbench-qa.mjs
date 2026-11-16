import {chromium} from '../../../frontend/node_modules/playwright/index.mjs'
const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1568,height:1003}});const errors=[]
p.on('pageerror',e=>errors.push(e.message))
await p.goto('http://localhost:5198/?import=project',{waitUntil:'networkidle'});await p.waitForTimeout(1500)
console.log('Workbench',await p.locator('body').innerText().then(x=>x.slice(0,1700)));console.log('errors',errors)
await p.screenshot({path:'E:/stock/videos/backing-intro/out/qa/workbench.png',fullPage:true});await b.close()
