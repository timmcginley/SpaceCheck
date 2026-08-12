"""
Generate an SVG overlay showing IfcGrid lines, IfcSpace polygons and labels.

Usage (from repo root):
    python -m tools.overlay_svg --ifc "path/to/file.ifc" --out svg/overlay.svg

Functions are modular so you can import and call them from other scripts.
"""
import argparse
import os
from typing import List, Tuple, Dict, Optional

import ifcopenshell
import ifcopenshell.geom

# configure geom settings once
settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, False)

SVG_HEADER = ('<?xml version="1.0" encoding="utf-8"?>\n'
              '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n')
SVG_FOOTER = '</svg>\n'


def load_model(ifc_path: str):
    return ifcopenshell.open(ifc_path)


# --- grid helpers ---

def _axis_average(axis) -> Optional[List[float]]:
    try:
        curve = getattr(axis, 'AxisCurve', None)
        if curve is None and hasattr(axis, 'AxisLine'):
            curve = getattr(axis, 'AxisLine')
        pts = []
        if curve is None:
            return None
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


def _axis_line_position(axis) -> Optional[float]:
    """Extract a single constant coordinate from a grid axis line.

    For U axes we expect nearly-vertical lines and return the x coordinate.
    For V axes we expect nearly-horizontal lines and return the y coordinate.
    """
    try:
        coords = []
        if hasattr(axis, 'AxisCurve') and getattr(axis, 'AxisCurve') is not None:
            curve = axis.AxisCurve
            if hasattr(curve, 'Points') and curve.Points:
                for p in curve.Points:
                    values = getattr(p, 'Coordinates', None)
                    if values:
                        coords.append([float(c) for c in values])
            elif hasattr(curve, 'Pnt') and getattr(curve, 'Pnt') is not None:
                p = curve.Pnt
                values = getattr(p, 'Coordinates', None)
                if values:
                    coords.append([float(c) for c in values])
        elif hasattr(axis, 'AxisLine') and getattr(axis, 'AxisLine') is not None:
            line = axis.AxisLine
            if hasattr(line, 'Pnt') and getattr(line, 'Pnt') is not None:
                p = line.Pnt
                values = getattr(p, 'Coordinates', None)
                if values:
                    coords.append([float(c) for c in values])
            if hasattr(line, 'Direction') and getattr(line, 'Direction') is not None:
                d = line.Direction
                values = getattr(d, 'Coordinates', None)
                if values and coords:
                    # Use point+direction to infer line orientation, but preserve base coordinate
                    pass
        if not coords:
            return None
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        if dx < dy:
            return sum(xs) / len(xs)
        return sum(ys) / len(ys)
    except Exception:
        return None


def extract_grid_lines(model) -> Dict[str, Dict[str, List[float]]]:
    """Return dict of grid.GlobalId -> {'u_positions': [x], 'v_positions': [y], 'name': Name, 'storey': storey_id}."""
    grids = model.by_type('IfcGrid')
    result = {}
    for g in grids:
        u_positions = []
        v_positions = []
        for axis in getattr(g, 'UAxes', ()):
            pos = _axis_line_position(axis)
            if pos is not None:
                u_positions.append(pos)
        for axis in getattr(g, 'VAxes', ()):
            pos = _axis_line_position(axis)
            if pos is not None:
                v_positions.append(pos)
        if not u_positions or not v_positions:
            continue
        u_positions = sorted(set(round(x, 6) for x in u_positions))
        v_positions = sorted(set(round(y, 6) for y in v_positions))
        storey_id = None
        for rel in getattr(g, 'ContainedInStructure', ()):
            storey = getattr(rel, 'RelatingStructure', None)
            if storey is not None and storey.is_a('IfcBuildingStorey'):
                storey_id = storey.GlobalId
                break
        result[g.GlobalId] = {
            'name': getattr(g, 'Name', None),
            'globalid': g.GlobalId,
            'u_positions': u_positions,
            'v_positions': v_positions,
            'storey': storey_id,
        }
    return result


def extract_storey_grids(model):
    grid_lines = extract_grid_lines(model)
    storeys = {}
    for g in model.by_type('IfcBuildingStorey'):
        storeys[g.GlobalId] = {
            'name': getattr(g, 'Name', None) or g.GlobalId,
            'elevation': getattr(g, 'Elevation', 0.0) or 0.0,
            'grids': [],
        }
    for grid in grid_lines.values():
        storey_id = grid.get('storey')
        if storey_id and storey_id in storeys:
            storeys[storey_id]['grids'].append(grid)
        else:
            storeys.setdefault('unmapped', {'name': 'unmapped', 'elevation': 0.0, 'grids': []})['grids'].append(grid)
    return storeys


# --- SVG helpers ---

def _world_to_svg(x, y, bounds, w=1200, h=800, margin=20):
    minx, miny, maxx, maxy = bounds
    sx = (w - 2 * margin) / (maxx - minx)
    sy = (h - 2 * margin) / (maxy - miny)
    s = min(sx, sy)
    tx = -minx * s + margin
    return (x * s + tx, (maxy - y) * s + margin)  # flip Y for SVG


def _svg_line(x1, y1, x2, y2, bounds, stroke='#0000ff', stroke_width=1):
    a = _world_to_svg(x1, y1, bounds)
    b = _world_to_svg(x2, y2, bounds)
    return f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="{stroke}" stroke-width="{stroke_width}" />\n'


def _svg_text(x, y, text, bounds, font_size=12, fill='#000000'):
    a = _world_to_svg(x, y, bounds)
    return f'<text x="{a[0]:.2f}" y="{a[1]:.2f}" font-size="{font_size}" fill="{fill}">{text}</text>\n'


def generate_svg_overlay(ifc_path: str, out_path: str):
    model = load_model(ifc_path)
    storeys = extract_storey_grids(model)
    basename = os.path.splitext(os.path.basename(out_path))[0]
    base_dir = os.path.dirname(out_path) or '.'
    os.makedirs(base_dir, exist_ok=True)

    for storey_id, storey in storeys.items():
        if not storey['grids']:
            continue
        bounds = _bounds_from_storey(storey)
        svg_parts = [SVG_HEADER]
        for grid in storey['grids']:
            for x in grid['u_positions']:
                svg_parts.append(_svg_line(x, bounds[1] - 1000, x, bounds[3] + 1000, bounds, stroke='#0066cc', stroke_width=1))
            for y in grid['v_positions']:
                svg_parts.append(_svg_line(bounds[0] - 1000, y, bounds[2] + 1000, y, bounds, stroke='#0066cc', stroke_width=1))
            if grid['u_positions'] and grid['v_positions'] and grid['name']:
                svg_parts.append(_svg_text(grid['u_positions'][0], grid['v_positions'][0], grid['name'], bounds, font_size=14, fill='#0066cc'))
        svg_parts.append(SVG_FOOTER)
        storey_name = storey['name'].replace(' ', '_')[:50]
        out_file = os.path.join(base_dir, f"{basename}_{storey_name}.svg")
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(''.join(svg_parts))
        print(f'Wrote SVG overlay for storey {storey_name} to {out_file}')


# simple point-in-polygon adapted from main
def _point_in_polygon(x, y, poly):
    if not poly:
        return False
    inside = False
    n = len(poly)
    px, py = x, y
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > py) != (y2 > py)):
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if xint > px:
                inside = not inside
    return inside


# CLI
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ifc', required=True, help='IFC file path')
    parser.add_argument('--out', required=True, help='Output SVG path')
    args = parser.parse_args()
    generate_svg_overlay(args.ifc, args.out)
