/* Flat-ground navigation. Shared by the browser and deterministic Node tests. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.PetNavigation = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
    'use strict';
    const distance = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
    class Navigation {
        constructor({radius = 3.2, bodyRadius = .36, margin = .08, cell = .18, obstacles = [], water = [], bridges = [], rug = null, surfaces = []} = {}) {
            this.radius = radius - bodyRadius - margin;
            this.clearance = bodyRadius + margin;
            this.cell = cell;
            this.surfaces=surfaces;this.water = water; this.bridges = bridges; this.rug = rug;
            this.obstacles = [...obstacles, ...bridges.flatMap(b => [-1,1].map(side => ({
                kind:'rect', x:b.x+side*(b.w-b.rail)/2, z:b.z, w:b.rail, d:b.d
            })))];
            this.n = Math.floor(this.radius / cell);
            this.size = 2 * this.n + 1;
            this.nodes = [];
            for (let z = -this.n; z <= this.n; z++) for (let x = -this.n; x <= this.n; x++) {
                const p = {x: x * cell, z: z * cell};
                this.nodes.push({...p, gx: x, gz: z, valid: this.isWalkable(p)});
            }
        }
        isWalkable(p) {
            if (!Number.isFinite(p.x + p.z) || Math.hypot(p.x, p.z) > this.radius) return false;
            for (const w of this.water) {
                const distanceToWater = Math.hypot(Math.max(0,Math.abs(p.x-w.x)-w.w/2),Math.max(0,Math.abs(p.z-w.z)-w.d/2));
                // Only the deck corridor can override water exclusion. Ordinary props
                // and bridge rails below remain obstacles, including at the banks.
                if (distanceToWater <= this.clearance && !this.bridges.some(b =>
                    Math.abs(p.x-b.x) < b.w/2-b.rail-this.clearance && Math.abs(p.z-b.z) <= b.d/2)) return false;
            }
            for (const o of this.obstacles) {
                if (o.kind === 'rect') {
                    const c = Math.cos(o.angle || 0), s = Math.sin(o.angle || 0);
                    const dx = p.x - o.x, dz = p.z - o.z;
                    const x = c * dx + s * dz, z = -s * dx + c * dz;
                    // Rounded expansion of the original box, including corner clearance.
                    if (Math.hypot(Math.max(0, Math.abs(x) - o.w / 2), Math.max(0, Math.abs(z) - o.d / 2)) <= this.clearance) return false;
                } else if (distance(p, o) <= o.r + this.clearance) return false;
            }
            return true;
        }
        surfaceHeight(p) {
            const r=this.rug || {x:0,z:0,radius:1.68,fade:.16,base:.013,rise:.026};
            let height=r.base+r.rise*Math.max(0,Math.min(1,(r.radius-Math.hypot(p.x-r.x,p.z-r.z))/r.fade));
            for (const b of this.bridges) if (Math.abs(p.x-b.x)<=b.w/2 && Math.abs(p.z-b.z)<=b.d/2) {
                const t=(p.z-b.z)/b.d+.5;
                height=Math.max(height,b.base+b.rise*Math.sin(Math.PI*t)**2);
            }
            for(const s of this.surfaces)if(Math.abs(p.x-s.x)<=s.w/2&&p.z<=s.front&&p.z>=s.back){
                height=Math.max(height,s.base+s.rise*Math.max(0,Math.min(1,(s.front-p.z)/s.ramp)));
            }
            return height;
        }
        segmentClear(a, b) {
            const count = Math.max(1, Math.ceil(distance(a, b) / .035));
            for (let i = 0; i <= count; i++) {
                const k = i / count;
                if (!this.isWalkable({x: a.x + (b.x - a.x) * k, z: a.z + (b.z - a.z) * k})) return false;
            }
            return true;
        }
        index(x, z) { return (z + this.n) * this.size + x + this.n; }
        node(x, z) { return Math.abs(x) <= this.n && Math.abs(z) <= this.n ? this.nodes[this.index(x,z)] : null; }
        nearest(p) {
            let best = null, cost = Infinity;
            for (const node of this.nodes) if (node.valid) {
                const d = distance(p, node);
                if (d < cost) {cost = d; best = node;}
            }
            return best ? {x:best.x, z:best.z} : null;
        }
        route(from, to) {
            // Commands outside the stage or inside a prop are rejected, not silently re-targeted.
            if (!this.isWalkable(from) || !this.isWalkable(to)) return null;
            if (this.segmentClear(from,to)) return [to];
            const nearestConnected = (p) => this.nodes.filter(n => n.valid && this.segmentClear(p,n)).sort((a,b)=>distance(p,a)-distance(p,b))[0];
            const start = nearestConnected(from), end = nearestConnected(to);
            if (!start || !end) return null;
            const id = n => this.index(n.gx,n.gz), startId = id(start), endId = id(end);
            const open = new Set([startId]), costs = new Map([[startId,0]]), previous = new Map();
            while (open.size) {
                let current = null, priority = Infinity;
                for (const k of open) { const f = costs.get(k) + distance(this.nodes[k], end); if (f < priority) {current=k; priority=f;} }
                if (current === endId) {
                    const path = [to]; let p = current;
                    while (p !== startId) { path.unshift(this.nodes[p]); p = previous.get(p); }
                    path.unshift(start);
                    const result = []; let cursor = from;
                    for (let i = 0; i < path.length;) {
                        let far = i;
                        for (let j = i; j < path.length; j++) if (this.segmentClear(cursor,path[j])) far=j;
                        const point = {x:path[far].x,z:path[far].z}; result.push(point); cursor=point; i=far+1;
                    }
                    return result;
                }
                open.delete(current); const node = this.nodes[current];
                for (let dz=-1; dz<=1; dz++) for (let dx=-1; dx<=1; dx++) {
                    if (!dx && !dz) continue;
                    const next = this.node(node.gx+dx,node.gz+dz);
                    if (!next || !next.valid || !this.segmentClear(node,next)) continue;
                    if (dx && dz && (!this.node(node.gx+dx,node.gz).valid || !this.node(node.gx,node.gz+dz).valid)) continue;
                    const nextId=id(next), cost=costs.get(current)+distance(node,next);
                    if (cost < (costs.get(nextId) ?? Infinity)) {costs.set(nextId,cost);previous.set(nextId,current);open.add(nextId);}
                }
            }
            return null;
        }
        randomDestination(from, random = Math.random) {
            const valid = this.nodes.filter(n=>n.valid && distance(from,n)>.7);
            for (let i=0;i<20 && valid.length;i++) {
                const node=valid[Math.floor(random()*valid.length)], path=this.route(from,node);
                if (path) return path;
            }
            return null;
        }
    }
    const legacy = {
        sakura: [{x:-2.3,z:-1.5,r:.18},{x:2.15,z:-1.35,r:.24}],
        snow: [{x:-2,z:-1.2,r:.55},{x:1.9,z:-.9,r:.4},{x:1.2,z:-1.9,r:.62},{x:-1.1,z:-2.1,r:.34},{x:-2.5,z:-.8,r:.55},{x:2.5,z:-1.5,r:.5}],
        room: [{kind:'rect',x:-2.1,z:-1.3,w:.9,d:.9,angle:.4},{x:2.3,z:-1.3,r:.34},{x:1.9,z:-1.1,r:.22},{x:2.35,z:-.7,r:.22}],
        camp: [{x:1.7,z:.9,r:.4},{x:-2.2,z:-1.2,r:.85},{kind:'rect',x:.5,z:-2.3,w:2.4,d:.09}]
    };
    return {Navigation, legacy, distance};
});
