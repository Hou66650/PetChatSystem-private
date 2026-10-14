(()=>{if(new URLSearchParams(location.search).get('enter')!=='island')return;
document.documentElement.classList.add('island-arriving');
// Replay the arrival when the selected pet is ready, not while its model loads.
document.addEventListener('petchat:ready',()=>{document.documentElement.classList.remove('island-arriving');requestAnimationFrame(()=>requestAnimationFrame(()=>document.documentElement.classList.add('island-arriving')));},{once:true});
})();
