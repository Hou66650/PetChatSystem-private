// Bounds measured from the same original GLB files used by the desktop site.
export interface NativeAsset {
  id: string; name: string; path: string;
  cx: number; cy: number; cz: number; scale: number; triangles: number;
}
export const NATIVE_ASSETS: NativeAsset[] = [
  {
    "id": "cat",
    "name": "猫咪（原模型）",
    "path": "/static/models/petchat-cat-v3/cat.glb",
    "cx": 0.020420233719050884,
    "cy": 0.49986473633907735,
    "cz": 0.004636526107788086,
    "scale": 1.4262879932274934,
    "triangles": 154155
  },
  {
    "id": "room",
    "name": "雾林温室（原模型）",
    "path": "/static/models/home-islands/room.glb",
    "cx": 2.748093605041504,
    "cy": 1.2191603183746338,
    "cz": 2.2307896614074707,
    "scale": 0.05681514817763381,
    "triangles": 1355779
  },
  {
    "id": "sakura",
    "name": "樱花庭院（原模型）",
    "path": "/static/models/home-islands/sakura.glb",
    "cx": 0.031198740005493164,
    "cy": 0.09605813026428223,
    "cz": 0.09882831573486328,
    "scale": 0.152979891751046,
    "triangles": 362894
  },
  {
    "id": "snow",
    "name": "雪境木屋（原模型）",
    "path": "/static/models/home-islands/snow.glb",
    "cx": -0.04212832450866699,
    "cy": -0.2488541603088379,
    "cz": -0.10121464729309082,
    "scale": 0.14942109223319217,
    "triangles": 337204
  },
  {
    "id": "camp",
    "name": "山岭营地（原模型）",
    "path": "/static/models/home-islands/camp.glb",
    "cx": 0.07385778427124023,
    "cy": 0.40000009536743164,
    "cz": 0.007249355316162109,
    "scale": 0.12900674711133797,
    "triangles": 236854
  }
];

export const NATIVE_PETS: NativeAsset[] = [
  { id: 'cat', name: '团子 · 猫咪', path: '/static/models/petchat-cat-v3/cat.glb',
    cx: 0.020420233719050884, cy: 0.49986473633907735, cz: 0.004636526107788086,
    scale: 1.4262879932274934, triangles: 154155 },
  { id: 'shiba', name: '球球 · 柴犬', path: '/static/models/petchat-shiba-v4/qiuqiu.glb',
    cx: -0.009536638855934143, cy: 0.5295296667318325, cz: -0.0243472158908844,
    scale: 1.596365467929971, triangles: 160839 },
  { id: 'husky', name: '雪球 · 哈士奇', path: '/static/models/petchat-husky-v3/xueqiu.glb',
    cx: -0.0030482448637485504, cy: 0.5893443611857947, cz: -0.024509400129318237,
    scale: 1.2961548146872839, triangles: 169146 },
  { id: 'shepherd', name: '德牧', path: '/static/models/petchat-shepherd-v2/shepherd.glb',
    cx: -0.01590704917907715, cy: 0.5894881194108166, cz: -0.06000429391860962,
    scale: 1.3179154062696679, triangles: 163530 }
];
