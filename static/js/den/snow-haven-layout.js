/* Shared by Blender authoring and the selected snow scene's navigator. */
(function(root){
    const layout = {
        "radius": 3.2,
        "rug": {"x":0,"z":0,"radius":0,"fade":0.1,"base":0.025,"rise":0},
        "obstacles": [
            {"x":-1.85,"z":-1.65,"r":0.59},
            {"x":-0.75,"z":-2.35,"r":0.47},
            {"x":-2.5,"z":-0.65,"r":0.44},
            {"kind":"rect","x":1.25,"z":-1.72,"w":1.6,"d":1.5},
            {"kind":"rect","x":2.22,"z":-1.6,"w":0.38,"d":0.72},
            {"kind":"rect","x":2.3,"z":0.15,"w":0.65,"d":1.65},
            {"x":-2.35,"z":0.55,"r":0.28},
            {"kind":"rect","x":-1.4,"z":1.72,"w":1.8,"d":1.18},
            {"x":0.3,"z":2.4,"r":0.19},
            {"x":0.8,"z":2.35,"r":0.19},
            {"x":1.35,"z":1.8,"r":0.13},
            {"x":2.35,"z":-0.8,"r":0.15},
            {"x":0.0,"z":-2.8,"r":0.15},
            {"kind":"rect","x":0,"z":-2.83,"w":3.7,"d":0.13}
        ],
        "interest_points": [{"name":"rest","x":0,"z":0},{"name":"lodge","x":0.3,"z":0},{"name":"play","x":0.65,"z":0.5}]
    };
    if(typeof module==='object'&&module.exports)module.exports=layout;
    else root.SnowHavenLayout=layout;
})(typeof window!=='undefined'?window:globalThis);
