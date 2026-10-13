(function (root, factory) {
    const api=factory();
    if (typeof module==='object' && module.exports) module.exports=api;
    else root.PetLocomotion=api;
})(typeof window!=='undefined'?window:globalThis,function(){
    'use strict';
    class Controller {
        constructor({navigation,model,animate,rest,random=Math.random,speed=.55,strideSpeed=.55,forwardOffset=0}) {
            Object.assign(this,{navigation,model,animate,rest,random,speed,strideSpeed,forwardOffset});
            this.baseSpeed=speed; this.idleRange=[4,9];
            this.enabled=true; this.path=[]; this.velocity=0; this.wait=3; this.blocked=false; this.owner='idle'; this.moves=0;
        }
        setBehavior(policy){
            this.speed=this.baseSpeed*(policy?.speedScale||1);
            this.idleRange=policy?.idleSeconds||[4,9];
            if(!this.path.length)this.wait=this.idleRange[0];
        }
        interrupt(seconds=2.5) {this.path=[];this.velocity=0;this.wait=Math.max(this.wait,seconds);this.owner='interaction';}
        toggle(enabled) {this.enabled=enabled;this.interrupt(1);if (!enabled && !this.blocked) this.animate('idle',1);}
        goTo(point) {
            const path=this.navigation.route(this.model.position,point);
            if (!path) return false;
            this.path=path;this.wait=0;this.owner='command';return true;
        }
        safePlacement() {
            const p=this.navigation.nearest(this.model.position);
            if (p) {this.model.position.x=p.x;this.model.position.z=p.z;}
        }
        update(dt,blocked=false) {
            if (blocked) {if (!this.blocked) this.interrupt();this.blocked=true;return;}
            this.blocked=false;
            if (!this.enabled && this.owner!=='command') return;
            if (!this.path.length) {
                this.velocity=0;this.wait-=dt;
                if (this.wait<=0 && this.enabled) {this.path=this.navigation.randomDestination(this.model.position,this.random)||[];this.owner='wander';this.wait=3;}
                if (!this.path.length) return;
            }
            const point=this.path[0], p=this.model.position, dx=point.x-p.x, dz=point.z-p.z, distance=Math.hypot(dx,dz);
            if (distance<.012) {
                p.x=point.x;p.z=point.z;this.path.shift();
                if (!this.path.length) {this.velocity=0;this.moves++;this.wait=this.idleRange[0]+this.random()*(this.idleRange[1]-this.idleRange[0]);this.owner='rest';this.rest(this.random());}
                return;
            }
            const target=Math.atan2(dx,dz)+this.forwardOffset;
            const angle=Math.atan2(Math.sin(target-this.model.rotation.y),Math.cos(target-this.model.rotation.y));
            this.model.rotation.y += angle*Math.min(1,dt*7);
            const remaining=distance + this.path.slice(1).reduce((sum,n,i)=>sum+Math.hypot(n.x-this.path[i].x,n.z-this.path[i].z),0);
            const desired=Math.min(this.speed,Math.sqrt(2*.8*remaining))*Math.max(0,Math.cos(angle));
            this.velocity+=Math.max(-1.3*dt,Math.min(1.3*dt,desired-this.velocity));
            const step=Math.min(distance,this.velocity*dt), next={x:p.x+dx/distance*step,z:p.z+dz/distance*step};
            if (!this.navigation.segmentClear(p,next)) {this.interrupt(2);this.animate('idle',1);return;}
            p.x=next.x;p.z=next.z;
            this.animate('walk',Math.max(.08,this.velocity/this.strideSpeed));
        }
        debug(){return {enabled:this.enabled,owner:this.owner,path:this.path.map(p=>({x:p.x,z:p.z})),speed:this.velocity,wait:this.wait,moves:this.moves,legal:this.navigation.isWalkable(this.model.position),radius:this.navigation.radius};}
    }
    return {Controller};
});
