const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('visitFixture',{request:(url,body)=>ipcRenderer.invoke('fixture',url,body)});
