const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const sharp=require('sharp');
const root=path.resolve(__dirname,'..'),design=path.join(root,'art/paw-heart-park-v1/design'),review=path.join(root,'art/paw-heart-park-v1/review');
fs.mkdirSync(review,{recursive:true});
(async()=>{
 for(const file of fs.readdirSync(design).filter(name=>name.endsWith('.svg')).sort()){
  const source=path.join(design,file),output=path.join(review,file.replace(/\.svg$/,'.png'));
  try{await sharp(source).png().toFile(output);}catch(error){throw new Error('SVG render failed: '+file+' '+error.message);}
  assert(fs.statSync(output).size>10000,'empty render '+file);console.log(output);
 }
 console.log('PASS editable SVG concept sheets rendered to PNG');
})().catch(e=>{console.error(e);process.exitCode=1;});
