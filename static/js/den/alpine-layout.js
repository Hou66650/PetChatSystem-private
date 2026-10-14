/* Metres in Three.js coordinates; shared with Blender authoring. */
(function(root){
 const layout = {
  "radius":5.6,
  "rug":{"x":0,"z":0,"radius":0,"fade":0.1,"base":0.035,"rise":0},
  "water":[{"x":0,"z":1.9,"w":11.2,"d":0.65}],
  "bridges":[{"x":0,"z":1.9,"w":2.9,"d":3.1,"rail":0.13,"base":0.035,"rise":0.27}],
  "obstacles":[
   {"kind":"rect","x":1.7,"z":-2.9,"w":2.8,"d":2.2},
   {"x":-1.4,"z":-3.6,"r":0.85},
   {"kind":"rect","x":0,"z":-4.85,"w":8.5,"d":0.85},
   {"x":-4.3,"z":-1.8,"r":0.8},{"x":4.5,"z":-1.5,"r":0.6},
   {"x":-3.8,"z":0.2,"r":0.55},{"x":4.2,"z":0.25,"r":0.5},
   {"x":-2.3,"z":-1.55,"r":0.3},{"x":3.2,"z":-0.4,"r":0.28}
  ],
  "interest_points":[{"name":"rest","x":0,"z":-0.5},{"name":"bridge","x":0,"z":3.7},{"name":"play","x":2,"z":0}]
 };
 if(typeof module==='object'&&module.exports)module.exports=layout;else root.AlpineLayout=layout;
})(typeof window!=='undefined'?window:globalThis);
