"""Teaching experiments with seeded whole-plant azimuth and the verified C core.
Each function constructs its own inputs. No hidden previous-experiment state.
"""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from canopyteach import Architecture,Mesh,LEAF,assimilation,solar_position,CanopyLight,simulate_day
from canopyteach.geometry import leaf
from canopyteach.simulation import prepare_canopy,integrate
from canopyteach.plotting import draw_mesh as _draw_mesh,crop_figure as _crop_figure,structures as _structures,daily_figure

def style():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.grid':False,'figure.dpi':100,'savefig.dpi':150})

def equal_axes(ax,points=None):
    """Equal numeric ranges and equal box edges: one metre has the same scale.
    This changes the view only, never the model vertices. Include negative Z
    for an isolated naturally curved leaf instead of clipping at ground level.
    """
    if points is None:
        limits=np.array([ax.get_xlim3d(),ax.get_ylim3d(),ax.get_zlim3d()])
        lo,hi=limits[:,0],limits[:,1]
    else:
        points=np.asarray(points,dtype=float);lo=points.min(axis=0);hi=points.max(axis=0)
    center=(lo+hi)/2;radius=max(float(np.max(hi-lo))*1.08,.01)/2
    ax.set(xlim=(center[0]-radius,center[0]+radius),
           ylim=(center[1]-radius,center[1]+radius),
           zlim=(center[2]-radius,center[2]+radius))
    ax.set_box_aspect((1,1,1));ax.set_proj_type('ortho')
    return ax

def draw_mesh(ax,mesh,*args,**kwargs):
    artist=_draw_mesh(ax,mesh,*args,**kwargs)
    equal_axes(ax,mesh.vertices)
    return artist

def crop_figure(config=None):
    fig=_crop_figure(config)
    for ax in fig.axes:equal_axes(ax)
    return fig

def structures(configs):
    fig=_structures(configs)
    # Keep comparisons on a common cubic scale as well as equal XYZ units.
    limits=np.array([[ax.get_xlim3d(),ax.get_ylim3d(),ax.get_zlim3d()] for ax in fig.axes])
    bounds=np.vstack([limits[:,:,0].min(axis=0),limits[:,:,1].max(axis=0)])
    for ax in fig.axes:equal_axes(ax,bounds)
    return fig

def leaf_variants(angle=60,length=.80,width=.16):
    """One-factor comparisons using the unchanged original maize generator.
    length is midrib arc length, width a profile input, not a rotated XYZ span.
    """
    variants={
        'Reference':dict(length=.65,width=.12,angle=35.),
        'Length only':dict(length=float(length),width=.12,angle=35.),
        'Width only':dict(length=.65,width=float(width),angle=35.),
        'Angle only':dict(length=.65,width=.12,angle=float(angle))}
    meshes={};records=[]
    for name,parameters in variants.items():
        v,f=leaf(**parameters)
        m=Mesh(v,f,np.full(len(f),LEAF),np.zeros(len(f),int),np.zeros(len(f),int),1)
        meshes[name]=m
        records.append({'case':name,**parameters,'area_m2':float(m.area.sum()),
                        'xyz_span_m':np.ptp(v,axis=0).tolist()})
    return meshes,records

def geometry_example(angle=60,length=.80,width=.16):
    style();fig=plt.figure(figsize=(10,8));meshes,records=leaf_variants(angle,length,width)
    points=np.vstack([m.vertices for m in meshes.values()])
    for i,record in enumerate(records):
        ax=fig.add_subplot(2,2,i+1,projection='3d');m=meshes[record['case']]
        draw_mesh(ax,m,title=f"{record['case']}: L={record['length']:.2f} m, W={record['width']:.2f} m\nangle={record['angle']:g} deg; area={record['area_m2']:.4f} m2")
        equal_axes(ax,points)
    print('case          input L (m)  input W (m)  angle (deg)  actual area (m2)')
    for r in records:print(f"{r['case']:13s} {r['length']:10.2f} {r['width']:12.2f} {r['angle']:12.1f} {r['area_m2']:17.7f}")
    print('All panels share XYZ limits and equal metre scales. Angle rotates a fixed shape; L/W changes actual area.')
    fig.tight_layout();return fig

def geometry_trial(lower=20,upper=70,*,length=.65,width=.12):
    c=replace(Architecture(),lower_angle=float(lower),upper_angle=float(upper),
              leaf_length=float(length),leaf_width=float(width));m=prepare_canopy(c)
    info={'lower_angle':float(lower),'upper_angle':float(upper),'ground_area_m2':m.ground_area,'LAI':m.lai,
          'leaf_area_m2':float(m.area[m.leaf_mask].sum()),**m.report}
    return m,info

def print_geometry(info):
    print(f"Source {info['source_rows']}x{info['source_columns']} -> central {info['central_rows']}x{info['central_columns']}")
    print(f"Ground={info['ground_area_m2']:.6f} m2; leaf area={info['leaf_area_m2']:.9f} m2; LAI={info['LAI']:.6f}")
    print(f"Central stems={info['central_stem_plants']}; plants contributing leaf fragments={info['contributing_plants']}")
    print('Whole-plant azimuth:',info['plant_azimuth_mode'],'; reproducible seed:',info['plant_azimuth_seed'])

def day(lower=20,upper=70,step_minutes=30,ray_spacing=.005):
    return simulate_day(replace(Architecture(),lower_angle=float(lower),upper_angle=float(upper)),
                        step_minutes=int(step_minutes),ray_spacing=float(ray_spacing),threads=4)

def light_example(hour=12,step_minutes=30,ray_spacing=.005):
    style();m=prepare_canopy();sp=solar_position('2026-06-21',float(hour),31,121,8)
    light=CanopyLight(m,ray_spacing=ray_spacing,threads=4).trace(sp['sun'],1500)
    r=day(step_minutes=step_minutes,ray_spacing=ray_spacing)
    fig=plt.figure(figsize=(11,4.2));ax=fig.add_subplot(121,projection='3d')
    draw_mesh(ax,m.mesh,light.total,title=f'Central crop PPFD: clock {hour:g} h',cmap='YlOrRd',vmax=1800)
    ax=fig.add_subplot(122)
    for name,color in [('leaf','#247c6b'),('stem','#ac845c'),('escape','#8ba3b7')]:
        ax.plot(r.hours,[s[name+'_umol_s']/m.ground_area for s in r.statistics],label=name,color=color)
    ax.set(xlabel='Clock hour',ylabel='umol photons / m2 ground / s',title='Photon rates through the day');ax.legend()
    fig.tight_layout();return sp,light,r,fig

def photon_rates(r):
    return np.array([s['leaf_umol_s']/r.mesh.ground_area for s in r.statistics])

def photon_table(r):
    s=r.summary
    print('Daily photons / mol per m2 ground')
    for name,key in [('leaf','daily_leaf_intercepted_mol_photons_m2_ground'),('stem','daily_stem_intercepted_mol_photons_m2_ground'),
                     ('escape','daily_escape_mol_photons_m2_ground'),('incident','daily_incident_mol_photons_m2_ground')]:
        print(f'{name:9s} {s[key]:.6f}')

def aq_example():
    style();q=np.linspace(0,1800,400);fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    axes[0].plot(q,assimilation(q),color='#247c6b',lw=2);axes[0].scatter([0,800,1600],assimilation([0,800,1600]),c='#ca9d3e')
    axes[0].set(xlabel='PPFD / umol photons m-2 s-1',ylabel='Net A / umol CO2 m-2 leaf s-1',title='Supplied A-Q equation')
    vals=[assimilation([1600,0]).sum(),assimilation([800,800]).sum()]
    bars=axes[1].bar(['1600 + 0','800 + 800'],vals,color=['#ca9d3e','#247c6b']);axes[1].bar_label(bars,fmt='%.3f',padding=4)
    axes[1].set(ylabel='Total CO2 / umol s-1',title='Two 1 m2 leaves; equal photons',ylim=(0,50))
    fig.tight_layout();return fig

def validated_student_rate(fn):
    if not callable(fn):return None,'supplied A-Q (exercise not defined in this kernel)'
    try:
        q=np.array([0.,100.,800.,1600.]);value=fn(q)
        if value is None:return None,'supplied A-Q (exercise returns None)'
        value=np.asarray(value,dtype=float)
        if value.shape!=q.shape or not np.isfinite(value).all() or not np.allclose(value,assimilation(q),rtol=1e-8,atol=1e-8):
            return None,'supplied A-Q (student equation has not passed its self-check)'
        return fn,'student A-Q (self-check passed)'
    except (TypeError,ValueError,NameError,ZeroDivisionError):
        return None,'supplied A-Q (student equation needs correction)'

def design_trial(lower=10,upper=55,rate_function=None,step_minutes=30,ray_spacing=.005):
    rate,label=validated_student_rate(rate_function);results={}
    for name,a,b in [('baseline',20,70),('my_design',float(lower),float(upper))]:
        r=day(a,b,step_minutes=step_minutes,ray_spacing=ray_spacing)
        if rate is not None:
            mask=r.mesh.leaf_mask;net=np.zeros_like(r.ppfd);value=np.asarray(rate(r.ppfd[:,mask]),float)
            if value.shape!=r.ppfd[:,mask].shape or not np.isfinite(value).all():raise ValueError('student A-Q must return a finite array matching Q')
            net[:,mask]=value;r.net_a=net;r.canopy_a_ground=net@r.mesh.area/r.mesh.ground_area
            r.daily_carbon_leaf=integrate(net,r.hours*3600)*1e-6
            r.summary['daily_net_mol_co2_m2_ground']=float(integrate(r.canopy_a_ground,r.hours*3600)*1e-6)
        r.summary['exercise_leaf_equation']=label;r.summary['selected_lower_angle']=a;r.summary['selected_upper_angle']=b
        results[name]=r
    return results,label

def print_design(results):
    print('case       LAI       daily photons       daily net CO2 (both per m2 ground)')
    for name,r in results.items():
        s=r.summary;print(f"{name:10s} {s['lai']:.6f} {s['daily_leaf_intercepted_mol_photons_m2_ground']:16.6f} {s['daily_net_mol_co2_m2_ground']:18.9f}")

def save_experiment(results,folder):
    p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    data={name:r.summary for name,r in results.items()}
    (p/'experiment.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return p
