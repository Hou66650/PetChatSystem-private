/* Shared authoring/navigation dimensions in Three.js coordinates (metres).
 * Blender reads the JSON literal below; do not add expressions inside it. */
(function (root) {
    const layout = {
        "water": [{"x": 0, "z": 1.3, "w": 6.6, "d": 0.64}],
        "bridges": [{"x": 0, "z": 1.3, "w": 1.9, "d": 2.3, "rail": 0.09, "rise": 0.18, "base": 0.013}],
        "rug": {"x": 0, "z": -0.9, "radius": 1.05, "fade": 0.105, "base": 0.013, "rise": 0.026}
    };
    if (typeof module === 'object' && module.exports) module.exports = layout;
    else root.SakuraRiverLayout = layout;
})(typeof window !== 'undefined' ? window : globalThis);
