import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util import shape
from ifcopenshell.util.element import get_container

# Set up geometry settings for area calculation
settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, False)

#TODO add office check and atrium and meeting rooms https://timmcginley.github.io/41936/Project/index.html#s05-meeting-rooms

# get the model
num = "10"
part = "D"
year = "26"
#file = ifcopenshell.open('models/ARCH_B112_IFC4.ifc')
loc ="C:/Users/TIMMC/OneDrive - Danmarks Tekniske Universitet/Skrivebord/36"+year+part+"/BIM/"

file_loc = loc + num + '/'+year+'-'+num+'-'+part+'-ARCH.ifc'
file = ifcopenshell.open(file_loc)
#file = ifcopenshell.open(loc + num + '/26-01-C-Existing building308.ifc')

spaces = file.by_type("IfcSpace")
print("IFC SCHEMA: " + file.schema)

desk_count = 0



def is_desk(element):
    if element.is_a("IfcBuildingElementProxy") or element.is_a("IfcFurniture"):
        name = (element.Name or "").lower()
        obj_type = (element.ObjectType or "").lower()
        return "desk" in name or "desk" in obj_type
    return False


print("Team: " + num+" "+year+" "+part)
print("IFC SCHEMA: " + file.schema)

if file.schema == "IFC4" or file.schema == "IFC4X3":
    schema = "[PASS] " + file.schema
    furn = file.by_type("IfcFurniture")
    for f in furn:
        if is_desk(f):
            desk_count += 1
else:
    schema = "[FAIL] " + file.schema 


# get the spaces and calculate their areas
print("There are {} spaces in the IFC file:" .format(len(spaces)))


def get_area(space):    
    # Try direct numeric attributes first
    def _value_to_number(val):
        try:
            return float(getattr(val, 'wrappedValue', val))
        except Exception:
            try:
                return float(val)
            except Exception:
                return None

    for attr in ("Area", "NetFloorArea", "GrossFloorArea"):
        if hasattr(space, attr):
            v = getattr(space, attr)
            n = _value_to_number(v)
            if n is not None:
                return n

    # Look in property sets for area-like properties
    if hasattr(space, 'IsDefinedBy'):
        for rel in space.IsDefinedBy:
            propdef = getattr(rel, 'RelatingPropertyDefinition', None)
            if propdef is None:
                continue
            if propdef.is_a('IfcPropertySet'):
                for prop in getattr(propdef, 'HasProperties', ()): 
                    if prop.is_a('IfcPropertySingleValue'):
                        name = str(getattr(prop, 'Name', '')).lower()
                        if 'area' in name:
                            nominal = getattr(prop, 'NominalValue', None)
                            n = _value_to_number(nominal)
                            if n is not None:
                                return n

    # Try geometry-based calculation (may raise RuntimeError if representation is NULL)
    try:
        shape_data = ifcopenshell.geom.create_shape(settings, space)
        try:
            area = shape.get_footprint_area(shape_data.geometry)
            return float(area)
        except Exception:
            pass
    except RuntimeError:
        # Representation is NULL or other geometry error; fall through
        pass
    except Exception:
        pass

    return None


def get_storey(space, model):
    # 1) Preferred: use get_container util (works in many cases)
    try:
        container = get_container(space)
        if container is not None and container.is_a('IfcBuildingStorey'):
            return container
    except Exception:
        pass

    # 2) Check common inverse relations on the space itself
    for rel_name in ('IsContainedInStructure', 'ContainedInStructure', 'IsDefinedBy'):
        if hasattr(space, rel_name):
            for rel in getattr(space, rel_name):
                for attr in ('RelatingStructure', 'RelatingBuildingStorey', 'RelatingSpatialStructure'):
                    struct = getattr(rel, attr, None)
                    if struct is not None and struct.is_a('IfcBuildingStorey'):
                        return struct

    # 3) Scan RelContainedInSpatialStructure relations in the model
    try:
        for rel in model.by_type('IfcRelContainedInSpatialStructure'):
            related = getattr(rel, 'RelatedElements', ())
            if space in related:
                for attr in ('RelatingStructure', 'RelatingBuildingStorey', 'RelatingSpatialStructure'):
                    struct = getattr(rel, attr, None)
                    if struct is not None and struct.is_a('IfcBuildingStorey'):
                        return struct
    except Exception:
        pass

    # 4) Scan storeys and their element containment relations
    try:
        for storey in model.by_type('IfcBuildingStorey'):
            if hasattr(storey, 'ContainsElements'):
                for rel in storey.ContainsElements:
                    elems = getattr(rel, 'RelatedElements', ())
                    if space in elems:
                        return storey
            if hasattr(storey, 'IsDecomposedBy'):
                for rel in storey.IsDecomposedBy:
                    if getattr(rel, 'RelatedObjects', None) is not None and space in rel.RelatedObjects:
                        return storey
    except Exception:
        pass

    return None

aud = "[FAIL] "
multi= "[FAIL] "
library= "[FAIL] "
cafe= "[FAIL] "
atrium= "[FAIL] "
office = 0
total_area = 0
for space in spaces:
    space_area = get_area(space)
    storey = get_storey(space, file)
    area_str = f"{round(space_area,2)}m2" if space_area is not None else 'N/A'
    total_area += space_area if space_area is not None else 0
    if ("auditorium" in space.LongName.lower()):
        aud = "[PASS] " + space.LongName +"\t" + area_str
    if ("cafe" in space.LongName.lower()):
        cafe = "[PASS] " + space.LongName +"\t" + area_str
    if ("library" in space.LongName.lower()):
        if space_area is not None and space_area >= 100:
            library = "[PASS] " + space.LongName +"\t" + area_str
        else :
            library = "[FAIL] " + space.LongName +"\t" + area_str + " (too small)"
    if ("atrium" in space.LongName.lower()):
        atrium = "[PASS] " + space.LongName +"\t" + area_str
    if ("office" in space.LongName.lower()):
        office += space_area if space_area is not None else 0
    if ("multi" in space.LongName.lower()):
        if space_area is not None and space_area >= 250:
            multi = "[PASS] " + space.LongName +"\t" + area_str
        else :
            multi = "[FAIL] " + space.LongName +"\t" + area_str + " (too small)"
    #print(f"{space.GlobalId} : {space.Name} \t ({area_str})  \t{space.LongName}\t{storey.Name if storey else 'No Storey'}")


print("Test 01 Sche = "+ schema)
print("Test 02 Audi = "+ aud)
print("Test 03 Mult = "+ multi)
print("Test 04 Libr = "+ library)
print("Test 05 cafe = "+ cafe)
print("Test 06 Atri = "+ atrium)
print("Test 07 Desk = "+ str(desk_count))
print("total office = "+ str(round(office, 2))+" m2")
print("total area = "+ str(round(total_area, 2))+" m2")


import json
import math
import os


def _axis_average(axis):
    """Return average XYZ for an IfcGridAxis by sampling its AxisCurve points."""
    try:
        curve = getattr(axis, 'AxisCurve', None)
        if curve is None and hasattr(axis, 'AxisLine'):
            curve = getattr(axis, 'AxisLine')
        pts = []
        if curve is None:
            return None
        # Many Ifc curve types expose a Points or Points attribute
        if hasattr(curve, 'Points') and curve.Points:
            for p in curve.Points:
                coords = getattr(p, 'Coordinates', None)
                if coords:
                    pts.append([float(c) for c in coords])
        elif hasattr(curve, 'Pnt') and getattr(curve, 'Pnt') is not None:
            p = curve.Pnt
            coords = getattr(p, 'Coordinates', None)
            if coords:
                pts.append([float(c) for c in coords])
        # Fallback: try to use placement if present
        if not pts and hasattr(axis, 'ObjectPlacement') and axis.ObjectPlacement is not None:
            try:
                rel = axis.ObjectPlacement.RelativePlacement
                loc = getattr(rel, 'Location', None)
                if loc is not None and getattr(loc, 'Coordinates', None):
                    coords = loc.Coordinates
                    pts.append([float(c) for c in coords])
            except Exception:
                pass

        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] if len(p) > 2 else 0.0 for p in pts]
        return [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)]
    except Exception:
        return None


def _collect_grid_lines(grid):
    """Collect two lists of axis averages for U and V axes from an IfcGrid."""
    u_avgs = []
    v_avgs = []
    try:
        for a in getattr(grid, 'UAxes', ()):
            av = _axis_average(a)
            if av is not None:
                u_avgs.append(av)
    except Exception:
        pass
    try:
        for a in getattr(grid, 'VAxes', ()):
            av = _axis_average(a)
            if av is not None:
                v_avgs.append(av)
    except Exception:
        pass
    return u_avgs, v_avgs


def generate_grid_squares_for_model(model):
    """Generate grid squares from IfcGrid entities in the model.

    Returns a dict mapping grid.GlobalId -> {'xs': [x coords], 'ys': [y coords], 'squares': [((x0,y0),(x1,y1)), ...]}
    """
    grids = model.by_type('IfcGrid')
    result = {}
    for g in grids:
        u_avgs, v_avgs = _collect_grid_lines(g)
        if not u_avgs or not v_avgs:
            continue
        # We project to XY plane: take x from u_avgs and y from v_avgs or vice-versa.
        xs = sorted(list({round(a[0], 6): a[0] for a in u_avgs}.values()))
        ys = sorted(list({round(a[1], 6): a[1] for a in v_avgs}.values()))
        # Ensure at least two lines in each direction
        if len(xs) < 2 or len(ys) < 2:
            continue
        squares = []
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                x0, x1 = xs[i], xs[i + 1]
                y0, y1 = ys[j], ys[j + 1]
                centroid = [(x0 + x1) / 2.0, (y0 + y1) / 2.0]
                squares.append({
                    'i': i,
                    'j': j,
                    'corners': [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                    'centroid_xy': centroid,
                })
        result[g.GlobalId] = {
            'name': getattr(g, 'Name', None),
            'globalid': g.GlobalId,
            'xs': xs,
            'ys': ys,
            'squares': squares,
        }
    return result


def _get_space_centroid(space):
    """Attempt to compute a centroid for an IfcSpace using placement or geometry."""
    try:
        # Try placement
        if getattr(space, 'ObjectPlacement', None) is not None:
            lp = space.ObjectPlacement
            rel = getattr(lp, 'RelativePlacement', None)
            if rel is not None and getattr(rel, 'Location', None) is not None:
                loc = rel.Location
                coords = getattr(loc, 'Coordinates', None)
                if coords:
                    x = float(coords[0])
                    y = float(coords[1])
                    z = float(coords[2]) if len(coords) > 2 else 0.0
                    return [x, y, z]
    except Exception:
        pass

    # Fallback: use geometry vertices average
    try:
        sd = ifcopenshell.geom.create_shape(settings, space)
        geom = sd.geometry
        verts = None
        # try common attribute names
        for name in ('verts', 'vertices', 'Vertices'):
            if hasattr(geom, name):
                verts = getattr(geom, name)
                break
        # Some geometry representations expose a flat list
        if verts and isinstance(verts, (list, tuple)) and len(verts) >= 3:
            coords = [float(v) for v in verts]
            # group into triples
            pts = list(zip(*(iter(coords),) * 3))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            zs = [p[2] for p in pts]
            return [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)]
    except Exception:
        pass
    return None


def _get_space_bbox(space):
    """Compute axis-aligned bounding box for a space from its geometry vertices.

    Returns (minx, miny, minz, maxx, maxy, maxz) or None on failure.
    """
    try:
        sd = ifcopenshell.geom.create_shape(settings, space)
        geom = sd.geometry
        verts = None
        for name in ('verts', 'vertices', 'Vertices'):
            if hasattr(geom, name):
                verts = getattr(geom, name)
                break
        if not verts:
            return None
        coords = [float(v) for v in verts]
        if len(coords) < 3:
            return None
        # group into triples
        pts = list(zip(*(iter(coords),) * 3))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
    except Exception:
        return None


def _get_space_mesh(space):
    """Extract triangle mesh data from a space using ifcopenshell.util.shape.

    If the geometry exposes a tree, preserve it for a faster ray-based containment
    method when available.
    """
    try:
        sd = ifcopenshell.geom.create_shape(settings, space)
        geom = sd.geometry
        verts_arr = shape.get_vertices(geom, is_2d=False)
        faces_arr = shape.get_faces(geom)
        if verts_arr is None or faces_arr is None:
            return None

        verts = [tuple(float(v) for v in row) for row in verts_arr]
        faces = [tuple(int(i) for i in row) for row in faces_arr if len(row) == 3]
        if not verts or not faces:
            return None

        xs = [p[0] for p in verts]
        ys = [p[1] for p in verts]
        zs = [p[2] for p in verts]
        return {
            'verts': verts,
            'faces': faces,
            'min_x': min(xs),
            'max_x': max(xs),
            'min_y': min(ys),
            'max_y': max(ys),
            'min_z': min(zs),
            'max_z': max(zs),
            'tree': getattr(geom, 'tree', None),
        }
    except Exception:
        return None


def _ray_intersections_with_tree(origin, direction, tree):
    """Attempt to count ray intersections using a geometry tree if available."""
    if tree is None:
        return None

    method_names = (
        'ray_cast',
        'raycast',
        'intersect_ray',
        'intersect',
        'ray',
        'trace',
    )
    for name in method_names:
        if hasattr(tree, name):
            method = getattr(tree, name)
            try:
                result = method(origin, direction)
            except TypeError:
                try:
                    result = method(origin[0], origin[1], origin[2], direction[0], direction[1], direction[2])
                except Exception:
                    continue
            if isinstance(result, int):
                return result
            if isinstance(result, bool):
                return 1 if result else 0
            if hasattr(result, '__len__'):
                return len(result)
    return None


def _cross(u, v):
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _ray_intersects_triangle(origin, direction, v0, v1, v2):
    eps = 1e-9
    edge1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    edge2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    h = _cross(direction, edge2)
    a = _dot(edge1, h)
    if abs(a) < eps:
        return False
    f = 1.0 / a
    s = (origin[0] - v0[0], origin[1] - v0[1], origin[2] - v0[2])
    u = f * _dot(s, h)
    if u < 0.0 or u > 1.0:
        return False
    q = _cross(s, edge1)
    v = f * _dot(direction, q)
    if v < 0.0 or (u + v) > 1.0:
        return False
    t = f * _dot(edge2, q)
    return t > eps


def _point_in_mesh(cx, cy, z, mesh):
    """Return True if the point is inside the mesh using a vertical ray cast."""
    if mesh is None:
        return False
    if cx < mesh['min_x'] or cx > mesh['max_x'] or cy < mesh['min_y'] or cy > mesh['max_y']:
        return False

    origin = (cx, cy, mesh['min_z'] - 1.0)
    direction = (0.0, 0.0, 1.0)

    tree = mesh.get('tree')
    if tree is not None:
        count = _ray_intersections_with_tree(origin, direction, tree)
        if count is not None:
            return (count % 2) == 1

    count = 0
    for tri in mesh['faces']:
        v0 = mesh['verts'][tri[0]]
        v1 = mesh['verts'][tri[1]]
        v2 = mesh['verts'][tri[2]]
        if _ray_intersects_triangle(origin, direction, v0, v1, v2):
            count += 1
    return (count % 2) == 1


def _convex_hull_2d(points):
    """Compute 2D convex hull (Monotone chain) for a set of (x,y) points."""
    pts = sorted(set(points))
    if len(pts) <= 1:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Concatenate lower and upper to get full hull; omit last point of each (it's the start of the other)
    hull = lower[:-1] + upper[:-1]
    return hull


def _get_space_polygon(space):
    """Extract a 2D polygon for the space by projecting its geometry vertices to XY and returning their convex hull."""
    try:
        sd = ifcopenshell.geom.create_shape(settings, space)
        geom = sd.geometry
        verts = None
        for name in ('verts', 'vertices', 'Vertices'):
            if hasattr(geom, name):
                verts = getattr(geom, name)
                break
        if not verts:
            return None
        coords = [float(v) for v in verts]
        if len(coords) < 3:
            return None
        pts = list(zip(*(iter(coords),) * 3))
        # project to XY
        xy = [(p[0], p[1]) for p in pts]
        # remove duplicates
        xy = list({(round(x, 6), round(y, 6)) for x, y in xy})
        if not xy:
            return None
        hull = _convex_hull_2d(xy)
        return hull
    except Exception:
        return None


def _point_in_polygon(x, y, poly):
    """Ray-casting point-in-polygon test. poly is list of (x,y) vertices."""
    if not poly:
        return False
    inside = False
    n = len(poly)
    px, py = x, y
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        # check if edge intersects ray to the right of point
        if ((y1 > py) != (y2 > py)):
            xinters = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
            # compute actual intersection x coordinate: x1 + (py-y1)*(x2-x1)/(y2-y1)
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if xint > px:
                inside = not inside
    return inside


def assign_spaces_to_grid_squares(model, out_json_path='grid_spaces.json', out_dir=None):
    """For each storey, assign nearest IfcSpace to each grid square centroid and write JSON.

    If out_dir is provided it will be used as the directory to write the JSON file. Otherwise
    a directory named using the module-level `num` variable will be created in the current
    working directory and the JSON will be written there.
    """
    grids = generate_grid_squares_for_model(model)
    storeys = list(model.by_type('IfcBuildingStorey'))
    # prepare space centroids and storey mapping
    spaces = model.by_type('IfcSpace')
    space_info = {}
    for s in spaces:
        cent = _get_space_centroid(s)
        bbox = _get_space_bbox(s)
        poly = _get_space_polygon(s)
        mesh = _get_space_mesh(s)
        st = get_storey(s, model)
        space_info[s.GlobalId] = {
            'space': s,
            'centroid': cent,
            'bbox': bbox,
            'polygon': poly,
            'mesh': mesh,
            'storey': st
        }

    output = {}
    for storey in storeys:
        z = getattr(storey, 'Elevation', 0.0) or 0.0
        floor_key = storey.Name or storey.GlobalId
        output[floor_key] = {
            'storey_globalid': storey.GlobalId,
            'elevation': z,
            'grids': [],
        }
        for gridid, g in grids.items():
            grid_entry = {'grid_globalid': gridid, 'squares': []}
            for sq in g['squares']:
                cx, cy = sq['centroid_xy']
                centroid3 = [cx, cy, z]
                assigned = None
                # Assign by containment using the precise polygon footprint when available
                for sid, info in space_info.items():
                    if info['storey'] is None:
                        continue
                    if info['storey'].GlobalId != storey.GlobalId:
                        continue
                    mesh = info.get('mesh')
                    if mesh and _point_in_mesh(cx, cy, z, mesh):
                        assigned = info['space']
                        break
                    poly = info.get('polygon')
                    if poly and _point_in_polygon(cx, cy, poly):
                        assigned = info['space']
                        break
                    # fallback to bbox check when both mesh and polygon are unavailable
                    if mesh is None and poly is None:
                        bbox = info.get('bbox')
                        if bbox is None:
                            continue
                        minx, miny, minz, maxx, maxy, maxz = bbox
                        if (minx <= cx <= maxx) and (miny <= cy <= maxy):
                            assigned = info['space']
                            break

                # Only use containment: do not fall back to nearest-space.
                assigned_id = getattr(assigned, 'GlobalId', None) if assigned else None
                assigned_name = getattr(assigned, 'LongName', None) if assigned else None

                grid_entry['squares'].append({
                    'i': sq['i'],
                    'j': sq['j'],
                    'centroid': centroid3,
                    'assigned_space_globalid': assigned_id,
                    'assigned_space_name': assigned_name,
                })
            output[floor_key]['grids'].append(grid_entry)

    # write to json into per-building folder
    try:
        if out_dir is None:
            out_dir = os.path.join(os.getcwd(), f'building_{num}')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, out_json_path)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"Wrote grid-space assignments to {out_path}")
    except Exception as e:
        print("Failed to write JSON:", e)


if __name__ == '__main__':
    # Example run: generate grid->space mapping and write to file
    try:
        # write output into a folder per building number
        default_out_dir = os.path.join(os.getcwd(), 'outputs', num)
        assign_spaces_to_grid_squares(file, out_json_path='grid_spaces.json', out_dir=default_out_dir)
    except Exception as e:
        print('Error assigning spaces to grid squares:', e)