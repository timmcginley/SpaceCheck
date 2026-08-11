import ifcopenshell
import ifcopenshell.geom
import sys
from ifcopenshell.util import shape

settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, False)

print('shape module attrs:')
print(sorted([a for a in dir(shape) if not a.startswith('_')]))
print('shape has geometry attr?', hasattr(shape, 'geometry'))
if hasattr(shape, 'geometry'):
    geommod = shape.geometry
    print('shape.geometry attrs:', sorted([a for a in dir(geommod) if not a.startswith('_')])[:50])

num = "02"
part = "D"
year = "26"
loc = "C:/Users/TIMMC/OneDrive - Danmarks Tekniske Universitet/Skrivebord/36" + year + part + "/BIM/"
file_loc = loc + num + '/' + year + '-' + num + '-' + part + '-ARCH.ifc'
print('Trying to open:', file_loc)
try:
    f = ifcopenshell.open(file_loc)
except Exception as e:
    print('OPEN_FAIL', e)
    sys.exit(1)

spaces = f.by_type('IfcSpace')
print('Spaces count:', len(spaces))
if not spaces:
    sys.exit(0)

s = spaces[0]
print('Inspecting space:', getattr(s, 'GlobalId', None), getattr(s, 'LongName', None))
try:
    sd = ifcopenshell.geom.create_shape(settings, s)
except Exception as e:
    print('CREATE_SHAPE_FAIL', e)
    sys.exit(1)

geom = sd.geometry
print('\nGEOMETRY ATTRS:')
print(sorted([a for a in dir(geom) if not a.startswith('_')]))
print('\nHAS TREE:', hasattr(geom, 'tree'))
if hasattr(geom, 'tree'):
    t = geom.tree
    print('\nTREE ATTRS:')
    print(sorted([a for a in dir(t) if not a.startswith('_')]))
    # Probe for likely methods
    probe = ['ray', 'intersect', 'intersections', 'ray_trace', 'raytrace', 'ray_cast', 'intersect_ray', 'aabb', 'bbox_query', 'query', 'intersects']
    for name in probe:
        if hasattr(t, name):
            print('METHOD', name, getattr(t, name))
else:
    print('No geometry.tree attribute on this geometry object')
    # Inspect verts/faces to see geometry layout for manual ray intersection
    for name in ('verts', 'faces', 'faces_tri', 'polyhedral_faces_without_holes', 'polyhedral_faces_with_holes'):
        if hasattr(geom, name):
            val = getattr(geom, name)
            try:
                ln = len(val)
            except Exception:
                ln = None
            print(f"HAS {name}: len={ln}")
            if ln:
                sample = list(val)[:min(10, ln)]
                print(f"SAMPLE {name}:", sample)

# Test some other element types for tree support
for tname in ['IfcSpace','IfcWall','IfcSlab','IfcBuildingElementProxy']:
    elems = f.by_type(tname)
    if not elems:
        continue
    e = elems[0]
    print(f"\nELEMENT TYPE {tname} first id {getattr(e,'GlobalId',None)}")
    try:
        sd2 = ifcopenshell.geom.create_shape(settings, e)
        g2 = sd2.geometry
        print('  has tree', hasattr(g2,'tree'))
        if hasattr(g2,'tree'):
            t2 = g2.tree
            print('  tree attrs', sorted([a for a in dir(t2) if not a.startswith('_')])[:50])
    except Exception as ex:
        print('  create_shape fail', ex)
    if hasattr(g2,'faces_tri'):
        v=getattr(g2,'faces_tri')
        print('  faces_tri len', len(v), 'sample', list(v)[:10])
