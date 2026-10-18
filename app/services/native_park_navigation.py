"""Bounded A* over the exact shared park layout. Never calls an AI provider."""
import heapq
import math
from . import park_navigation as nav

def route(start, end):
    if nav.segment(*start, *end):
        return [dict(x=end[0], z=end[1])]
    step = nav.LAYOUT['grid']
    points = {(i,j):(i*step,j*step) for i in range(-23,24) for j in range(-18,19)
              if nav.inside(i*step,j*step)}
    candidates = sorted(points, key=lambda k:math.dist(start,points[k]))
    first = next((k for k in candidates if nav.segment(*start,*points[k])), None)
    if first is None:
        return []
    dist={first:math.dist(start,points[first])}; parent={}; queue=[(0,first)]; seen=set()
    while queue:
        _,k=heapq.heappop(queue)
        if k in seen:continue
        seen.add(k);p=points[k]
        if nav.segment(*p,*end):
            path=[end,p]
            while k in parent:k=parent[k];path.append(points[k])
            path.reverse()
            # Smooth only through fully validated free-space segments.
            result=[];last=start
            while path:
                far=max(i for i,q in enumerate(path) if nav.segment(*last,*q))
                last=path[far];result.append(dict(x=last[0],z=last[1]));path=path[far+1:]
            return result
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            n=(k[0]+dx,k[1]+dz)
            if n not in points or not nav.segment(*p,*points[n]):continue
            cost=dist[k]+math.dist(p,points[n])
            if cost>=dist.get(n,float('inf')):continue
            parent[n]=k;dist[n]=cost
            heapq.heappush(queue,(cost+math.dist(points[n],end),n))
    return []
