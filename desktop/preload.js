const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('paitDesktop',{
 command:(name,data)=>ipcRenderer.invoke('desktop:command',name,data),
 subscribeMotion:callback=>{const listener=(_event,data)=>callback(data);ipcRenderer.on('desktop:motion',listener);return ()=>ipcRenderer.removeListener('desktop:motion',listener);},
 subscribe:callback=>{const listener=(_event,data)=>callback(data);ipcRenderer.on('desktop:state',listener);return ()=>ipcRenderer.removeListener('desktop:state',listener);}
});
