// Keep the existing browser-test entry point; exercise real Flask transactions.
// Screenshots, stage models, mobile layout and cleanup are verified by this harness.
const {spawnSync}=require('child_process'),fs=require('fs'),path=require('path'),os=require('os');
const local=path.join(os.homedir(),'.conda','envs','qijin666','python.exe');
const python=process.env.TEST_PYTHON||(fs.existsSync(local)?local:'python');
const result=spawnSync(python,['-X','utf8','test/farm_direct_browser.py'],{cwd:path.resolve(__dirname,'..'),stdio:'inherit',windowsHide:true});
if(result.error)console.error(result.error);
process.exit(result.status??1);
