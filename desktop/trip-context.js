'use strict';
const {Motion}=require('./motion');
class TripContext{
 constructor(origin,paired,generation){
  Object.assign(this,paired,{origin,generation,alive:true,window:null,manifest:null,modelLoaded:false,
   sensing:false,action:'idle',actionSerial:0,poseReady:false,actions:[],recentActions:[],autonomous:true,motion:new Motion(0,0),target:null,events:[],busy:false,chatBusy:false,speechBusy:false,
   lastWalk:Date.now(),lastCursor:Date.now(),lastContext:Date.now(),lastFrame:Date.now(),lastContact:Date.now(),
   lastSensor:0,lastPing:0,lastSample:0,animationUntil:0,sensorBusy:false,sensor:null,
   status:'正在准备宠物与饰品',reaction:'idle',timers:new Set(),requests:new Set(),accessoriesLoaded:new Set()});
 }
 signal(timeout){const c=new AbortController();this.requests.add(c);return {signal:AbortSignal.any([c.signal,AbortSignal.timeout(timeout)]),release:()=>this.requests.delete(c)};}
 every(fn,ms){const timer=setInterval(()=>{if(this.alive)fn();},ms);this.timers.add(timer);}
 dispose(){
  if(!this.alive)return;this.alive=false;
  for(const timer of this.timers)clearInterval(timer);this.timers.clear();
  for(const controller of this.requests)controller.abort();this.requests.clear();
  this.deliveryDispatcher?.dispose();
  this.sensor?.kill();this.sensor=null;this.motion.halt();this.events=[];this.target=null;this.sensing=false;
 }
}
module.exports={TripContext};
