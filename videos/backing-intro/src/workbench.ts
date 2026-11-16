import {Main,COMPONENTS,Caption,Wipe,Overlay,C} from './Main'
import {SHOTS,CAPTIONS,TRANSITIONS,SFX,TOTAL} from './timeline'
export const WORKBENCH={
 name:'Backing · 60 秒项目介绍',fps:30,width:1920,height:1080,total:TOTAL,background:C.bg,revision:'backing-v1',
 shots:SHOTS.map(s=>({id:s.id,label:s.section,from:s.from,duration:s.duration,component:COMPONENTS[s.id],props:{...s},durationProp:'duration',cardId:s.id,schema:[{type:'textarea',key:'title',label:'标题',default:s.title},{type:'textarea',key:'subtitle',label:'说明',default:s.subtitle},{type:'color',key:'accent',label:'强调色',default:C.brand},{type:'number',key:'titleSize',label:'标题字号',default:s.id==='brand'?130:s.id==='outro'?140:s.id==='architecture'?90:72,min:48,max:150}]})),
 captions:CAPTIONS.map(s=>({...s,component:Caption,label:s.text,props:{text:s.text,duration:s.duration},durationProp:'duration',schema:[{type:'textarea',key:'text',label:'字幕',default:s.text},{type:'number',key:'fontSize',label:'字号',default:64,min:56,max:90},{type:'color',key:'color',label:'颜色',default:C.ink}]})),
 transitions:TRANSITIONS.map(s=>({...s,component:Wipe,label:'镜头淡接',props:{duration:s.duration},durationProp:'duration'})),
 overlays:[{id:'project-label',from:0,duration:TOTAL,component:Overlay,label:'品牌与演示说明'}],
 sfx:SFX.map(s=>({...s,label:s.id})),bgm:[{from:0,duration:TOTAL,src:'audio/bgm.wav',volume:.2}],order:['overlays','captions','transitions'],original:Main,
}
