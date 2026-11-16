export const TOTAL=1800
// Source: measured House Vibez beat times (analysis/beat_data.json), rounded once at 30fps.
export const SHOTS=[
 {id:'brand',from:0,duration:180,title:'让每一次判断',subtitle:'都有研究依据。',caption:'个人 A 股研究工作台',section:'PROJECT / BACKING'},
 {id:'dashboard',from:180,duration:236,title:'从市场概览，\n发现新线索。',subtitle:'行情 · 自选股 · 研究进展',caption:'在一个工作台，掌握市场与自选股。',section:'01 / OBSERVE'},
 {id:'strategy',from:416,duration:251,title:'筛选标的，\n验证新想法。',subtitle:'检索 · 参数 · 行情与信号',caption:'把一个研究想法，变成可检验的策略。',section:'02 / RESEARCH'},
 {id:'ai',from:667,duration:236,title:'向 AI 提问，\n把依据说清。',subtitle:'会话 · 研究依据 · 风险边界',caption:'从研究问题出发，整理依据与风险边界。',section:'03 / AGENT WORKSPACE'},
 {id:'dl',from:903,duration:294,title:'从历史出发，\n比较新可能。',subtitle:'Kronos-small / base\nTimesFM 2.5',caption:'切换预测模型，保留参数、区间与结果。',section:'04 / MODEL LAB'},
 {id:'history',from:1197,duration:267,title:'不止看收益，\n更要看风险。',subtitle:'资金曲线 · 回撤 · 交易成本',caption:'回看每一次实验，让判断经得起复核。',section:'05 / VALIDATE'},
 {id:'architecture',from:1464,duration:162,title:'从交互，到计算。',subtitle:'一个完整的项目实现',caption:'前端、API、数据与模型，各司其职。',section:'06 / UNDER THE HOOD'},
 {id:'outro',from:1626,duration:174,title:'Backing',subtitle:'研究有依据，判断可验证。',caption:'',section:'OBSERVE / RESEARCH / VALIDATE'},
] as const
// Measured in analysis/audio-offset.json: AAC output lags 1.27 frames.
export const OUTPUT_AUDIO_OFFSET_F=1.27
const align=(target:number,sourcePeak=0)=>Math.max(0,Math.round(target-sourcePeak-OUTPUT_AUDIO_OFFSET_F))
export const SFX=[
 {id:'brand-hit',from:align(33,4.65),duration:38,src:'audio/sfx/fs-812748.mp3',volume:.14,peakTarget:33},
 {id:'overview-in',from:align(202,1.95),duration:17,src:'audio/sfx/fs-485279.mp3',volume:1.7,peakTarget:202},
 {id:'search-type',from:align(416+18),duration:24,src:'audio/sfx/typing.wav',volume:.55,peakTarget:null},
 {id:'search-click',from:align(416+74,1.05),duration:10,src:'audio/sfx/fs-534103.mp3',volume:.5,peakTarget:490},
 {id:'ai-write',from:align(667+20),duration:77,src:'audio/sfx/typing.wav',volume:.25,peakTarget:null},
 {id:'forecast-reveal',from:align(927,1.95),duration:17,src:'audio/sfx/fs-485279.mp3',volume:1.5,peakTarget:927},
 {id:'history-in',from:align(1214,1.95),duration:17,src:'audio/sfx/fs-485279.mp3',volume:1.2,peakTarget:1214},
 {id:'outro-in',from:align(1634,1.95),duration:17,src:'audio/sfx/fs-485279.mp3',volume:1.7,peakTarget:1634},
 {id:'outro-stamp',from:align(1675,4.65),duration:38,src:'audio/sfx/fs-812748.mp3',volume:.26,peakTarget:1675},
] as const
export const CAPTIONS=SHOTS.filter(s=>s.caption).map(s=>({id:s.id+'-caption',from:s.from+12,duration:s.duration-12,text:s.caption}))
export const TRANSITIONS=SHOTS.slice(1).map(s=>({id:s.id+'-transition',from:s.from,duration:10}))
