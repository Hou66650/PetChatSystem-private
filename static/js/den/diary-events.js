/* Completed interactions only; one quiet report per kind/pet/minute, no frame-loop work. */
(function(){
    const sent=new Map(),pending=new Set();
    window.PetDiary={record(petId,kind){
        if(!['visit','pet','hand','feed','game','gaze','gesture'].includes(kind))return;
        document.dispatchEvent(new CustomEvent('pet-growth-interaction',{detail:{petId:Number(petId),kind}}));
        const key=petId+':'+kind,now=Date.now();
        if(pending.has(key)||now-(sent.get(key)||0)<60000)return;
        pending.add(key);
        fetch('/api/diary/events',{method:'POST',credentials:'same-origin',paitQuiet:true,
            headers:{'Content-Type':'application/json','X-Profile-Scope':window.COMPANION_SCOPE},
            body:JSON.stringify({petId:Number(petId),kind})})
            .then(r=>{if(r.ok){sent.set(key,now);document.dispatchEvent(new CustomEvent('pet-growth-recorded',{detail:{petId:Number(petId)}}));}}).catch(()=>{}).finally(()=>pending.delete(key));
    }};
})();
