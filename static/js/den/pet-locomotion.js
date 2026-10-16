(function (root, factory) {
    const api=factory();
    if (typeof module==='object' && module.exports) module.exports=api;
    else root.PetLocomotion=api;
})(typeof window!=='undefined'?window:globalThis,function(){
    'use strict';
    class Controller {
        constructor({navigation,model,animate,rest,random=Math.random,speed=.55,strideSpeed=.55,forwardOffset=0,gaits=null}) {
            Object.assign(this,{navigation,model,animate,rest,random,speed,strideSpeed,forwardOffset});
            this.baseSpeed=speed; this.idleRange=[4,9];
            this.gaits=gaits||{walk:strideSpeed};this.gait='walk';this.requestedGait='walk';this.acceleration=0;this.turnRate=0;
            this.enabled=true; this.path=[]; this.velocity=0; this.wait=3; this.blocked=false; this.owner='idle'; this.moves=0;
        }
        setBehavior(policy){
            this.speed=this.baseSpeed*(policy?.speedScale||1);
            this.idleRange=policy?.idleSeconds||[4,9];
            this.lively=policy?.mode==='lively';
            if(!this.path.length)this.wait=this.idleRange[0];
        }
        interrupt(seconds=2.5) {const dock=this.navigation.dock;this.path=dock&&Math.hypot(this.model.position.x-dock.entry.x,this.model.position.z-dock.entry.z)>.012?[{...dock.entry}]:[];this.velocity=0;this.acceleration=0;this.turnRate=0;this.wait=Math.max(this.wait,seconds);this.owner='interaction';}
        approachBowl(dock){
            if(this.navigation.dock||Math.hypot(this.model.position.x-dock.entry.x,this.model.position.z-dock.entry.z)>.02)return false;
            this.navigation.dock=dock;
            if(!this.navigation.segmentClear(this.model.position,dock.target)){this.navigation.dock=null;return false;}
            this.path=[{...dock.target}];this.requestedGait='walk';this.owner='agent';this.wait=0;return true;
        }
        toggle(enabled) {this.enabled=enabled;this.interrupt(1);if (!enabled && !this.blocked) this.animate('idle',1);}
        goTo(point,{gait='auto'}={}) {
            const path=this.navigation.route(this.model.position,point);
            if (!path) return false;
            const length=path.reduce((s,p,i)=>s+Math.hypot(p.x-(i?path[i-1]:this.model.position).x,p.z-(i?path[i-1]:this.model.position).z),0);
            this.requestedGait=gait==='auto'?(length>1.2?'trot':'walk'):gait;
            if(!this.gaits[this.requestedGait])this.requestedGait='walk';
            this.path=path;this.wait=0;this.owner='command';return true;
        }
        safePlacement() {
            this.navigation.dock=null;
            const p=this.navigation.nearest(this.model.position);
            if (p) {this.model.position.x=p.x;this.model.position.z=p.z;}
        }
        update(dt,blocked=false) {
            dt=Math.max(0,Math.min(.05,Number.isFinite(dt)?dt:0));
            if (blocked) {if (!this.blocked) this.interrupt();this.blocked=true;return;}
            this.blocked=false;
            if(!dt)return;
            if (!this.enabled && this.owner!=='command'&&!this.navigation.dock) return;
            if (!this.path.length) {
                this.velocity=0;this.acceleration=0;this.turnRate=0;this.wait-=dt;
                if (this.wait<=0 && this.enabled && this.autonomous!==false) {this.path=this.navigation.randomDestination(this.model.position,this.random)||[];this.requestedGait=this.lively&&this.gaits.trot?'trot':'walk';this.owner='wander';this.wait=3;}
                if (!this.path.length) return;
            }
            const p=this.model.position;
            // Consume reached waypoints in this frame; a route vertex is not a rest.
            // Retain the array identity used by CatLife to recognize its own route.
            while(this.path.length&&Math.hypot(this.path[0].x-p.x,this.path[0].z-p.z)<.012){
                const reached=this.path[0];
                if(!this.navigation.segmentClear(p,reached)){this.interrupt(2);this.animate('idle',1);return;}
                p.x=reached.x;p.z=reached.z;this.path.shift();
                if(this.navigation.dock&&Math.hypot(p.x-this.navigation.dock.entry.x,p.z-this.navigation.dock.entry.z)<.012)this.navigation.dock=null;
                if (!this.path.length) {this.velocity=0;this.acceleration=0;this.turnRate=0;this.gait='walk';this.moves++;this.wait=this.idleRange[0]+this.random()*(this.idleRange[1]-this.idleRange[0]);this.owner='rest';this.rest(this.random());return;}
            }
            const point=this.path[0],dx=point.x-p.x,dz=point.z-p.z,distance=Math.hypot(dx,dz);
            const retreat=this.navigation.dock&&Math.hypot(point.x-this.navigation.dock.entry.x,point.z-this.navigation.dock.entry.z)<.012;
            const target=retreat?0:Math.atan2(dx,dz)+this.forwardOffset;
            const angle=Math.atan2(Math.sin(target-this.model.rotation.y),Math.cos(target-this.model.rotation.y));
            const desiredTurn=Math.max(-3.2,Math.min(3.2,angle*7));
            this.turnRate+=(desiredTurn-this.turnRate)*(1-Math.exp(-dt*12));
            // Preserve angular momentum when a command changes sides. Taking the
            // absolute rate here used to reverse rotation instantly in one frame.
            const turn=this.turnRate*angle>0?Math.sign(angle)*Math.min(Math.abs(angle),Math.abs(this.turnRate*dt)):this.turnRate*dt;
            this.model.rotation.y += turn;
            this.turnRate=turn/dt;
            const remaining=distance + this.path.slice(1).reduce((sum,n,i)=>sum+Math.hypot(n.x-this.path[i].x,n.z-this.path[i].z),0);
            const maximum=this.navigation.dock?Math.min(this.speed,.22):this.speed*(this.requestedGait==='run'?2.8:this.requestedGait==='trot'?1.75:1);
            let cornerLimit=maximum;
            if(this.path.length>1){
                const next=this.path[1],nx=next.x-point.x,nz=next.z-point.z,length=Math.hypot(nx,nz);
                if(length>.001){
                    const cosine=Math.max(-1,Math.min(1,(dx*nx+dz*nz)/(distance*length)));
                    const cornerSpeed=maximum*Math.max(.12,(1+cosine)/2)**2;
                    cornerLimit=Math.sqrt(cornerSpeed**2+2*.65*Math.max(0,distance-.04));
                }
            }
            // A proportional arrival envelope eases the last few centimetres;
            // sqrt(distance) alone still hit the endpoint with a visible snap.
            const desired=Math.min(maximum,cornerLimit,remaining*1.8,Math.sqrt(2*.8*remaining))*Math.max(0,Math.cos(angle))**2;
            const acceleration=Math.max(-1.6,Math.min(1.1,(desired-this.velocity)*7));
            this.acceleration+=(acceleration-this.acceleration)*(1-Math.exp(-dt*12));
            // A slower command lowers the target, not the current velocity.
            // Brake through the same bounded acceleration instead of snapping
            // from run speed to walk speed in the first frame after goTo().
            this.velocity=Math.max(0,Math.min(Math.max(maximum,this.velocity),this.velocity+this.acceleration*dt));
            const alignment=Math.max(0,Math.cos(angle)),step=Math.min(distance,this.velocity*dt*alignment), next={x:p.x+dx/distance*step,z:p.z+dz/distance*step};
            if (!this.navigation.segmentClear(p,next)) {this.interrupt(2);this.animate('idle',1);return;}
            p.x=next.x;p.z=next.z;
            const movingSpeed=step/dt;
            if(retreat){this.animate('walk',-movingSpeed/(this.gaits.walk||this.strideSpeed));return;}
            const turning=this.turnRate>0?'turnLeft':'turnRight';
            if(alignment<.3&&this.gaits[turning]){this.animate(turning,Math.abs(this.turnRate)/2);return;}
            const ratio=movingSpeed/this.speed;
            if(this.gait==='run'&&ratio<1.9)this.gait='trot';
            if(this.gait==='trot'&&ratio<1.1)this.gait='walk';
            if(this.gait==='walk'&&ratio>1.3&&this.gaits.trot)this.gait='trot';
            if(this.gait==='trot'&&ratio>2.15&&this.gaits.run)this.gait='run';
            this.animate(this.gait,movingSpeed/(this.gaits[this.gait]||this.strideSpeed));
        }
        debug(){return {enabled:this.enabled,owner:this.owner,gait:this.gait,requestedGait:this.requestedGait,path:this.path.map(p=>({x:p.x,z:p.z})),speed:this.velocity,wait:this.wait,moves:this.moves,legal:this.navigation.isWalkable(this.model.position),radius:this.navigation.radius};}
    }
    return {Controller};
});
