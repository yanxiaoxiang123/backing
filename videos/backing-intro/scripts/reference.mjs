import fs from 'node:fs/promises'
import {registerHooks} from 'node:module'
registerHooks({resolve(s,c,next){try{return next(s,c)}catch(e){if(s.startsWith('.'))return next(s+'.ts',c);throw e}}})
const path='C:/Users/13566/.codex/skills/video-shotcraft'
const j=JSON.parse(await fs.readFile(path+'/gallery/api/library.json','utf8'))
const names=['brand-ink-open','type-and-filter','document-typewriter-reveal','row-embed','outro-group-photo-launch']
await fs.writeFile('videos/backing-intro/analysis/gallery-selection.json',JSON.stringify(j.cards.filter(c=>names.includes(c.name)),null,2))
for(const name of names){const url=`https://vincentwei1021.github.io/video-shotcraft/media/${name}.mp4`;const r=await fetch(url);if(r.ok){await fs.mkdir('videos/backing-intro/analysis/references',{recursive:true});await fs.writeFile(`videos/backing-intro/analysis/references/${name}.mp4`,Buffer.from(await r.arrayBuffer()));console.log(name,'reference saved')}else console.log(name,r.status)}
