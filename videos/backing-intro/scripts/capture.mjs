import {registerHooks} from 'node:module'
registerHooks({resolve(s,c,next){try{return next(s,c)}catch(e){if(s.startsWith('.'))return next(s+'.ts',c);throw e}}})
import fs from 'node:fs/promises'
import {chromium} from '../../../frontend/node_modules/playwright/index.mjs'
const {mockResearchApi,bars,stocks,backtest}=await import('../../../frontend/e2e/fixtures/research.ts')
const OUT=new URL('../public/textures/',import.meta.url).pathname.replace(/^\/([A-Z]:)/,'$1')
const target=new URL('../src/layout.json',import.meta.url)
const names=['示例银行','示例地产','示例金融'];stocks.forEach((s,i)=>s.name=names[i])
const days=[];for(let d=new Date('2026-05-11T12:00:00Z');days.length<120;d.setUTCDate(d.getUTCDate()+1)){if(d.getUTCDay()%6!==0)days.push(d.toISOString().slice(0,10))}
bars.splice(0,bars.length,...days.map((date,i)=>{const c=10+Math.sin(i*.15)*.44+Math.sin(i*.41)*.12+i*.007;return {date,open:c-.06,close:c,high:c+.18,low:c-.22,volume:1200000+Math.round((1+Math.cos(i*.3))*460000),amount:15000000+i*12000}}))
const end=bars.at(-1);const future=['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30'];const prices=future.map((_,i)=>end.close+.03+Math.sin(i*.9)*.12)
const eq=bars.map((b,i)=>({date:b.date,total_value:100000+Math.sin(i*.1)*900+i*32,cash:65000,position_value:35000+Math.sin(i*.1)*900+i*32,position:3000}))
Object.assign(backtest,{start_date:days[0],end_date:end.date,total_return:3.86,final_capital:103860,annual_return:7.85,max_drawdown:2.31,sharpe_ratio:.84,portfolio_values:eq,win_rate:54.8,total_trades:18})
const browser=await chromium.launch({headless:true})
const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:2,reducedMotion:'reduce'})
const page=await context.newPage();page.setDefaultTimeout(6000);const errors=[];page.on('pageerror',e=>errors.push(e.message))
await mockResearchApi(page)
const thread={thread_id:'demo-research',title:'示例银行：趋势与风险复核',status:'idle',last_run_id:null,archived:false,created_at:'2026-10-23T09:00:00+08:00',updated_at:'2026-10-23T09:05:00+08:00'}
const reply='## 先核对依据，再讨论判断\n\n示例银行的短期均线呈上行排列，但近期量能未同步放大。可以把趋势作为研究线索，暂不把它等同于交易结论。\n\n### 三项交叉验证\n\n- **价格与趋势**：对比 20 日、60 日窗口，检查结论是否依赖单一参数。\n- **量能与成本**：纳入佣金、滑点及成交量约束，再比较策略表现。\n- **风险与边界**：观察最大回撤、仓位集中度，明确样本外验证区间。\n\n### 下一步怎么做\n\n使用同一历史区间运行均线策略回测，再对照模型预测。保存参数、输入区间和结果，便于之后复核。\n\n> 本页为固定演示数据。模型输出仅供研究，不构成投资建议。'
const forecast={stock_code:'sh.600000',model:'kronos-small',current_price:end.close,last_date:end.date,input_start:days[60],execution_time_ms:1380,prediction_dates:future,predicted_prices:prices,kline_data:bars.slice(-60),model_metadata:{device:'cuda:0',model_revision:'演示固定版本'},forecast_target:'ohlcv_amount'}
await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;let data
 if(path.endsWith('/dl/models'))data={models:['kronos-small','kronos-base','timesfm-2.5'].map(id=>({id,name:id==='timesfm-2.5'?'TimesFM 2.5':id.replace('kronos','Kronos'),available:true})),remote:{available:true}}
 else if(path.endsWith('/jobs/promo-dl'))data={id:'promo-dl',job_type:'dl_predict',status:'completed',progress:1,message:'实验完成',updated_at:'2026-10-23T01:05:00',result:{success:true,data:forecast}}
 else if(path.endsWith('/agent-chats/status'))data={backend:'native',available:true}
 else if(path.endsWith('/agent-chats'))data={threads:[thread,{...thread,thread_id:'demo-strategy',title:'均线策略：成本与回撤验证'}],total:2}
 else if(path.endsWith('/events'))return route.fulfill({contentType:'text/event-stream',body:': idle\n\n'})
 else if(path.includes('/agent-chats/'))data={thread,turns:[{id:1,thread_id:thread.thread_id,content:'帮我梳理示例银行的趋势依据，以及接下来应该怎样验证风险。',status:'completed',final_reply:reply,created_at:thread.created_at}],has_more:false,total_turns:1}
 else if(path.endsWith('/backtest/results'))data=Array.from({length:5},(_,i)=>({...backtest,id:41+i,strategy_name:['ma_cross','momentum','rsi_reversal','ma_cross','momentum'][i],stock_code:i%2?'sh.600036':'sh.600000',total_return:[3.86,-1.42,0.76,2.13,-.65][i]}))
 else if(path.endsWith('/settings/ai'))data={deepseek_configured:true}
 else return route.fallback()
 return route.fulfill({json:data,headers:path.endsWith('/backtest/results')?{'x-total-count':'5'}:{}})
})
await page.addInitScript(()=>{sessionStorage.setItem('backing_strategies_selectedStrategy',JSON.stringify('ma_cross'));sessionStorage.setItem('backing_strategies_dateRange',JSON.stringify(['2026-05-11','2026-10-23']));sessionStorage.setItem('backing_dl_dateRange',JSON.stringify(['2026-05-11','2026-10-23']));sessionStorage.setItem('backing_dl_stockCode',JSON.stringify('sh.600000'));sessionStorage.setItem('backing_dl_klineDays','60');sessionStorage.setItem('backing_dl_predictionDays','5');sessionStorage.setItem('backing_dl_experiment',JSON.stringify({kind:'predict',request:{stock_code:'sh.600000',model:'kronos-small',kline_days:60,prediction_days:5},key:'promo-demo',jobId:'promo-dl'}))})
const layout={}
async function settle(){await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(950);await page.mouse.move(2,2);await page.evaluate(()=>document.querySelectorAll('.ant-message').forEach(e=>e.remove()))}
async function capture(name,route,selectors){
 if(route)await page.goto('http://127.0.0.1:5174'+route,{waitUntil:'networkidle'})
 await page.evaluate(()=>scrollTo(0,0));await settle();layout[name]={pageH:await page.evaluate(()=>document.documentElement.scrollHeight),boxes:{}}
 await page.screenshot({path:OUT+name+'-full.png',fullPage:true})
 for(const [key,selector] of Object.entries(selectors)){
  const loc=page.locator(selector).first();if(!await loc.count()){console.log('missing',name,key,selector);continue}
  const box=await loc.boundingBox();if(!box)continue
  layout[name].boxes[key]={x:box.x,y:box.y+await page.evaluate(()=>scrollY),w:box.width,h:box.height,file:name+'-'+key+'.png'}
  const cdp=await context.newCDPSession(page);await cdp.send('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:4,mobile:false});await loc.screenshot({path:OUT+name+'-'+key+'.png',omitBackground:true});await cdp.send('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:2,mobile:false});await cdp.detach()
 }
 console.log('captured',name,JSON.stringify(layout[name]))
}
await capture('dashboard','/',{trend:'.dash-chart',market:'.dash-market',hero:'.dash-hero',watchlist:'.dash-watchlist'})
await capture('stocks','/stocks',{table:'.stock-list-table',search:'.stock-list-search',panel:'.stock-list-table-panel'})
await page.getByRole('textbox',{name:'搜索股票代码或名称'}).fill('示例银行')
await settle()
await capture('stocksFiltered',null,{action:'.stock-row-actions button',table:'.stock-list-table',search:'.stock-list-search'})
await page.goto('http://127.0.0.1:5174/strategies?stock=sh.600000',{waitUntil:'networkidle'})
await page.getByRole('button',{name:/生成信号/}).first().click().catch(()=>{})

await page.getByRole('button',{name:/执行回测|开始回测|运行回测/}).first().click().catch(()=>{})
await settle()
await capture('strategy',null,{results:'.strategy-results-panel',chart:'.strategy-chart-preview',config:'.strategy-form-panel'})
await capture('ai','/workspace?thread_id=demo-research',{reply:'.chat-msg-assistant',conversation:'.chat-conversation',sidebar:'.chat-sidebar'})
layout.ai.blocks=await page.locator('.chat-markdown h2,.chat-markdown h3,.chat-markdown p,.chat-markdown li').evaluateAll(els=>els.map(e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height,tag:e.tagName}}))
await page.setViewportSize({width:780,height:1080});await settle()
const evidence=page.locator('.chat-markdown ul').first()
await evidence.screenshot({path:OUT+'ai-evidence.png'})
layout.ai.evidence=await evidence.boundingBox()
await page.setViewportSize({width:1920,height:1080})
await capture('dl','/dl-prediction',{chart:'.dl-chart-panel',result:'.dl-results-panel',config:'.dl-config-panel'})
await capture('history','/history',{table:'.ant-table',summary:'.backtest-history-summary'})
layout.history.rows=await page.locator('.ant-table-tbody tr').evaluateAll(els=>els.map(e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}}).filter(b=>b.h>0).slice(0,5))
await page.locator('.ant-table-tbody button').filter({hasText:/查\s*看/}).first().click();await settle()
await capture('detail',null,{drawer:'.ant-drawer-content',equity:'.history-equity-panel',metrics:'.backtest-detail-metrics'})
await fs.writeFile(target,JSON.stringify(layout,null,2));await fs.writeFile(new URL('../analysis/capture-errors.json',import.meta.url),JSON.stringify(errors))
await browser.close()
