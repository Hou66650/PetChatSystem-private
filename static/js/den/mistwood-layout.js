/* Shared metres: Three.js X/Z, Blender X/-Y. Water is never a walking surface. */
(function(root){
 const layout = {
  "radius": 7.8,
  "surfaces": [{"x":3,"w":2.2,"front":-3.05,"back":-4.75,"base":0.035,"rise":0.49,"ramp":0.70}],
  "rug": {
    "x": 0,
    "z": 0,
    "radius": 0,
    "fade": 0.1,
    "base": 0.035,
    "rise": 0
  },
  "water": [
    {
      "x": 0,
      "z": 1.8,
      "w": 15.6,
      "d": 1.0
    }
  ],
  "bridges": [
    {
      "x": 0,
      "z": 1.8,
      "w": 3.5,
      "d": 4.0,
      "rail": 0.18,
      "base": 0.035,
      "rise": 0.32
    }
  ],
  "obstacles": [
    {"kind":"rect","tag":"catHome","x":-4.4,"z":4.35,"w":0.19,"d":2.4},
    {"kind":"rect","tag":"catHome","x":-1.6,"z":4.35,"w":0.19,"d":2.4},
    {"kind":"rect","tag":"catHome","x":-3,"z":3.25,"w":2.8,"d":0.19},
    {"kind": "rect", "tag": "greenhouse", "x": 0.9, "z": -3.4, "w": 0.12, "d": 3.3},
    {"kind": "rect", "tag": "greenhouse", "x": 5.1, "z": -3.4, "w": 0.12, "d": 3.3},
    {"kind": "rect", "tag": "greenhouse", "x": 3, "z": -5.05, "w": 4.2, "d": 0.12},
    {"kind": "rect", "tag": "greenhouse", "x": 1.4, "z": -1.75, "w": 1, "d": 0.12},
    {"kind": "rect", "tag": "greenhouse", "x": 4.6, "z": -1.75, "w": 1, "d": 0.12},
    {"kind": "rect", "tag": "greenhouse", "x": 1.4, "z": -3.5, "w": 1, "d": 0.07},
    {"kind": "rect", "tag": "greenhouse", "x": 4.6, "z": -3.5, "w": 1, "d": 0.07},
    {"kind": "rect", "tag": "greenhouse", "x": 1.28, "z": -2.7, "w": 0.5, "d": 1.35},
    {"kind": "rect", "tag": "greenhouse", "x": 4.72, "z": -2.7, "w": 0.5, "d": 1.35},
    {"kind": "rect", "tag": "greenhouse", "x": 1.28, "z": -4.55, "w": 0.5, "d": 0.5},
    {"kind": "rect", "tag": "greenhouse", "x": 4.72, "z": -4.55, "w": 0.5, "d": 0.5},
    {
      "x": -4.7,
      "z": -2.8,
      "r": 0.65
    },
    {
      "x": -3.8,
      "z": -5.5,
      "r": 0.65
    },
    {
      "x": -6.0,
      "z": -0.2,
      "r": 0.65
    },
    {
      "x": 5.7,
      "z": -4.4,
      "r": 0.65
    },
    {
      "kind": "rect",
      "x": 0,
      "z": -6.6,
      "w": 10.3,
      "d": 1.2
    },
    {
      "kind": "rect",
      "x": -3.4,
      "z": -0.3,
      "w": 1.9,
      "d": 0.75
    },
    {
      "kind": "rect",
      "x": 3.7,
      "z": 4.3,
      "w": 1.8,
      "d": 0.6
    },
    {
      "x": 4.30253,
      "z": -5.8353,
      "r": 0.35
    },
    {
      "x": 2.71288,
      "z": -6.7233,
      "r": 0.35
    },
    {
      "x": 0.95211,
      "z": -7.18721,
      "r": 0.35
    },
    {
      "x": -0.86873,
      "z": -7.19776,
      "r": 0.35
    },
    {
      "x": -2.63476,
      "z": -6.7543,
      "r": 0.35
    },
    {
      "x": -4.2346,
      "z": -5.88478,
      "r": 0.35
    },
    {
      "x": -5.56733,
      "z": -4.64407,
      "r": 0.35
    },
    {
      "x": -6.54888,
      "z": -3.11042,
      "r": 0.35
    },
    {
      "x": -7.11734,
      "z": -1.38056,
      "r": 0.35
    }
  ],
  "interest_points": [
    {
      "name": "rest",
      "x": 0,
      "z": 0
    },
    {
      "name": "bridge",
      "x": 0,
      "z": 4.2
    },
    {
      "name": "garden",
      "x": -2.8,
      "z": -3.7
    },
    {
      "name": "play",
      "x": 2.6,
      "z": 0
    }
  ],
  "trees": [
    {
      "x": -4.7,
      "z": -2.8,
      "h": 7.3,
      "birch": false
    },
    {
      "x": -3.8,
      "z": -5.5,
      "h": 8.1,
      "birch": false
    },
    {
      "x": -6,
      "z": -0.2,
      "h": 6.2,
      "birch": true
    },
    {
      "x": 5.7,
      "z": -4.4,
      "h": 6.9,
      "birch": true
    },
    {
      "x": 4.30253,
      "z": -5.8353,
      "h": 3.8,
      "birch": true
    },
    {
      "x": 2.71288,
      "z": -6.7233,
      "h": 4.5,
      "birch": false
    },
    {
      "x": 0.95211,
      "z": -7.18721,
      "h": 5.199999999999999,
      "birch": false
    },
    {
      "x": -0.86873,
      "z": -7.19776,
      "h": 3.8,
      "birch": true
    },
    {
      "x": -2.63476,
      "z": -6.7543,
      "h": 4.5,
      "birch": false
    },
    {
      "x": -4.2346,
      "z": -5.88478,
      "h": 5.199999999999999,
      "birch": false
    },
    {
      "x": -5.56733,
      "z": -4.64407,
      "h": 3.8,
      "birch": true
    },
    {
      "x": -6.54888,
      "z": -3.11042,
      "h": 4.5,
      "birch": false
    },
    {
      "x": -7.11734,
      "z": -1.38056,
      "h": 5.199999999999999,
      "birch": false
    }
  ]
};
 if(typeof module==='object'&&module.exports)module.exports=layout;else root.MistwoodLayout=layout;
})(typeof window!=='undefined'?window:globalThis);
