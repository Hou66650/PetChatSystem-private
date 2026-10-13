/* Qiuqiu's facial layer is independent from locomotion and full-body clips. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ShibaExpression=api;})(typeof window!=='undefined'?window:globalThis,function(){
    'use strict';
    const acts={
        curious:{label:'歪头听你说',clip:'curious_listen'}, ears:{label:'竖耳听一听',clip:'ear_perk'},
        shy:{label:'害羞一下',clip:'shy_look'}, alert:{label:'认真望一望',clip:'alert_scan'},
        yawn:{label:'打个小哈欠',clip:'sleepy_yawn'}, affection:{label:'开心蹭蹭',clip:'affection'},
        surprise:{label:'咦，怎么啦',clip:'surprised'}, playBow:{label:'邀请你玩',clip:'play_bow'},
        wave:{label:'挥爪打招呼',clip:'paw_greeting'}, noseLick:{label:'舔舔小鼻子',clip:'nose_lick'},
        shake:{label:'抖抖毛',clip:'shake_off'}, greet:{label:'摇尾欢迎你',clip:'tail_greeting'}
    };
    function idleChoice(random,mode,previous){
        const pool=(mode==='calm'?['idle','ears','curious','yawn']:mode==='lively'?['curious','ears','greet','playBow','sniff','noseLick']:['idle','curious','ears','alert','sniff','noseLick','yawn']).filter(x=>x!==previous);
        return pool[Math.min(pool.length-1,Math.floor(Math.max(0,random)*pool.length))];
    }
    function closure(state,phase){
        const envelope=Math.sin(Math.PI*Math.max(0,Math.min(1,phase)))**2;
        if(state==='sleep')return 1;
        if(state==='yawn')return .99*envelope;
        if(state==='affection'||state==='petting')return .58*envelope;
        if(['happy','greet','playBow','wave'].includes(state))return .28*envelope;
        if(state==='shy')return .23*envelope;
        return 0;
    }
    class Controller {
        constructor(model){
            this.meshes=[];this.eyes=[];this.lids=[];this.elapsed=0;this.blinkAt=-10;this.amount=0;
            model.traverse(o=>{
                if(o.morphTargetDictionary&&'Blink_L' in o.morphTargetDictionary)this.meshes.push(o);
                if(o.isBone&&/^eye_[LR]$/.test(o.name))this.eyes.push({bone:o,position:o.position.clone(),scale:o.scale.clone()});
                if(o.isBone&&/^lid_[LR]$/.test(o.name))this.lids.push(o);
            });
        }
        blink(){this.blinkAt=this.elapsed;}
        update(dt,state,phase){
            this.elapsed+=Math.min(dt,.5);
            const age=this.elapsed-this.blinkAt;
            const blink=age>=0&&age<.23?Math.sin(Math.PI*age/.23)**2:0;
            const target=closure(state,phase);
            this.amount+=(target-this.amount)*(1-Math.exp(-dt*16));
            const value=Math.max(blink,this.amount);
            for(const m of this.meshes){
                m.morphTargetInfluences[m.morphTargetDictionary.Blink_L]=value;
                m.morphTargetInfluences[m.morphTargetDictionary.Blink_R]=value;
            }
            for(const e of this.eyes){e.bone.position.copy(e.position);e.bone.position.z-=.042*value;e.bone.scale.copy(e.scale);}
            for(const b of this.lids)b.scale.setScalar(value>.62?1:.001);
        }
        debug(){return {meshes:this.meshes.length,closure:this.amount,eyes:this.eyes.length};}
    }
    return {acts,idleChoice,closure,Controller};
});
