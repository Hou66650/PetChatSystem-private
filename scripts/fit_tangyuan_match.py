"""Fit annotated visible landmarks to a short, non-looping dog shot.

Requires numpy and scipy. The solution is a monocular artistic reconstruction,
not motion capture. Occluded feet remain explicitly marked as inferred.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from scipy.interpolate import PchipInterpolator

p=argparse.ArgumentParser();p.add_argument('--landmarks',required=True);p.add_argument('--annotations',required=True);p.add_argument('--output',required=True)
a=p.parse_args();land=json.loads(Path(a.landmarks).read_text());ann=json.loads(Path(a.annotations).read_text())
points={k:np.array(v) for k,v in land['points'].items()};pivot=np.array(land['head_pivot'])
keys=ann['keys'];times=np.array([k['source_frame']/30 for k in keys])
elev=np.deg2rad(55);distance=2.8;cam=np.array([0,-distance*np.cos(elev),.3+distance*np.sin(elev)])
right=np.array([1,0,0]);up=np.array([0,np.sin(elev),np.cos(elev)]);forward=np.cross(up,right)
focal=720*32/20.25

def project(v,angle=elev,height_offset=0):
    u=np.array([0,np.sin(angle),np.cos(angle)]);f=np.cross(u,right)
    v=v-cam-np.array([0,0,height_offset]);z=v@f
    return np.array([360+focal*(v@right)/z,640-focal*(v@u)/z])

def pose(v,k,name):
    if name in ('nose','crown'):
        v=Rotation.from_euler('xyz',k[3:6]).apply(v-pivot)+pivot
    return Rotation.from_euler('z',k[2]).apply(v)+np.array([k[0],k[1],0])

initial=np.array([[0,-.25,k['yaw'],k['pitch'],0,0,elev,0] for k in keys])
def residual(flat):
    params=flat.reshape(-1,8);r=[]
    for i,(k,q) in enumerate(zip(keys,params)):
        for name in ('nose','crown','tail'):
            r.extend((project(pose(points[name],q,name),q[6],q[7])-k['points'][name])/10)
        r.extend([(q[2]-k['yaw'])*3,(q[3]-k['pitch'])*1.5,q[4]*3,q[5]*5,(q[6]-elev)*.7,q[7]*.8])
    # Penalize velocity discontinuity while allowing the observed turn.
    for i in range(1,len(params)-1):
        before=(params[i]-params[i-1])/(times[i]-times[i-1])
        after=(params[i+1]-params[i])/(times[i+1]-times[i])
        r.extend((after-before)*np.array([.05,.05,.06,.06,.06,.06,.06,.06]))
    return r

lo=np.tile([-1.4,-2,-1.1,-.4,-.55,-.3,.35,-.8],len(keys));hi=np.tile([1.4,2,1.1,1.1,.55,.3,1.5,.8],len(keys))
solution=least_squares(residual,initial.flatten(),bounds=(lo,hi),max_nfev=300,ftol=1e-9,xtol=1e-9)
params=solution.x.reshape(-1,8);spline=PchipInterpolator(times,params,axis=0)

def unproject_ground(pixel,z,angle,height_offset):
    u=np.array([0,np.sin(angle),np.cos(angle)]);f=np.cross(u,right)
    direction=f+right*(pixel[0]-360)/focal-u*(pixel[1]-640)/focal
    camera=cam+np.array([0,0,height_offset])
    return camera+direction*((z-camera[2])/direction[2])

# Fit each visible foot in the ground plane at its annotated lift. Unknown
# feet use continuous key poses, rather than inventing measured observations.
feet_keys={name:[] for name in ('FL','FR','HL','HR')}
for i,(k,q) in enumerate(zip(keys,params)):
    for name in feet_keys:
        rest=points[name];lift=k.get('lifts',{}).get(name,0)
        if name in k['points']:
            world=unproject_ground(k['points'][name],rest[2]+lift,q[6],q[7])
            local=Rotation.from_euler('z',-q[2]).apply(world-np.array([q[0],q[1],0]))
            # IK reach is separately verified against the exported rig.
            delta=local-rest
            delta[:2]=np.clip(delta[:2],[-.14,-.22],[.14,.22])
        else:
            delta=np.array([k.get('inferred_dx',{}).get(name,0),k.get('inferred_dy',{}).get(name,0),lift])
        feet_keys[name].append(rest+delta+np.array([0,.025,.075]))
feet_splines={k:PchipInterpolator(times,np.array(v),axis=0) for k,v in feet_keys.items()}
frames=[]
for source_frame in range(keys[0]['source_frame'],keys[-1]['source_frame']+1):
    t=source_frame/30;q=spline(t)
    frames.append({'source_frame':source_frame,'source_time':t,'root':[float(q[0]),float(q[1]),0],'yaw':float(q[2]),'head_euler':q[3:6].tolist(),'camera_euler':[float(np.pi/2-q[6]),0,0],'camera_position':(cam+np.array([0,0,q[7]])).tolist(),'feet':{k:s(t).tolist() for k,s in feet_splines.items()}})
errors=[]
for k,q in zip(keys,params):
    for name in ('nose','crown','tail'):
        errors.append({'source_frame':k['source_frame'],'landmark':name,'pixels':float(np.linalg.norm(project(pose(points[name],q,name),q[6],q[7])-k['points'][name]))})
output={'camera':{'position':cam.tolist(),'rotation_euler':[float(np.pi/2-elev),0,0],'lens':32},'frames':frames,'annotation_method':'manual visible landmarks; occluded feet inferred','source_fps':30,'cut_source_frame':54,'solver_success':bool(solution.success),'reprojection_errors':errors,'rms_visible_head_tail_pixels':float(np.sqrt(np.mean([e['pixels']**2 for e in errors]))),'is_motion_capture':False,'owner_approved':False}
Path(a.output).write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps({'solver_success':output['solver_success'],'rms_pixels':output['rms_visible_head_tail_pixels'],'frames':len(frames)}))
