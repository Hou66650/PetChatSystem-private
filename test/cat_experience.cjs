// Repeatable companion acceptance gate. Uses isolated fixtures, never a user's browser session.
const {spawnSync}=require('node:child_process'),path=require('node:path');
const checks=['cat_return.cjs','cat_care.cjs','cat_life.cjs','cat_agent.cjs','cat_agent_navigation.cjs','cat_agent_scheduling.cjs','cat_autonomy.cjs','cat_relationship.cjs','cat_monitor.cjs','toy_immersive.cjs'];
for(const file of checks){const r=spawnSync(process.execPath,[path.join(__dirname,file)],{cwd:path.resolve(__dirname,'..'),stdio:'inherit',timeout:120000});if(r.error||r.status!==0){console.error('FAIL',file,r.error||r.status);process.exit(1);}}
console.log('PASS companion acceptance: care, movement, interruption, network recovery, relationship persistence, monitoring and toys');
