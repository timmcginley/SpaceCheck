import json
import os
import statistics
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_BUILDING = '02'


def load_grid(path=None, building=None):
    if path is None:
        if building is None:
            building = DEFAULT_BUILDING
        path = os.path.join(ROOT, 'outputs', building, 'grid_spaces.json')
        if not os.path.exists(path):
            # fall back to first available outputs/<num>/grid_spaces.json
            outputs_dir = os.path.join(ROOT, 'outputs')
            if os.path.isdir(outputs_dir):
                for sub in sorted(os.listdir(outputs_dir)):
                    candidate = os.path.join(outputs_dir, sub, 'grid_spaces.json')
                    if os.path.exists(candidate):
                        path = candidate
                        break
        # fallback to root default
        if not os.path.exists(path):
            path = os.path.join(ROOT, 'grid_spaces.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f), path


def load_colors(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'colors.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _label_contrast(hexcolor: str) -> str:
    """Return black or white text color for readable contrast against hexcolor."""
    try:
        c = hexcolor.lstrip('#')
        if len(c) == 3:
            r = int(c[0]*2, 16)
            g = int(c[1]*2, 16)
            b = int(c[2]*2, 16)
        else:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
        # relative luminance approximation
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return '#ffffff' if lum < 140 else '#000000'
    except Exception:
        return '#000000'


# Human-readable category names
CATEGORY_NAMES = {
    'O': 'Office',
    'SD': 'Student spaces',
    'MR': 'Meeting room',
    'C': 'Cafe / Kitchen / Dining',
    'MP': 'Multi-purpose',
    'AU': 'Auditorium',
    'AT': 'Atrium',
    'L': 'Material Library',
    'E': 'Entrance / Lobby / Reception',
    'W': 'WC / Shower / Restroom',
    'F': 'Fill',
    'V': 'Vertical circulation (Stair/Lift)',
    'H': 'Hall / Corridor',
    'T': 'Technical / MEP',
    'S': 'Shaft',
    'RF': 'Roof',
    'G': 'Garden',
    'ST': 'Storage',
    'B': 'Bike / Bicycle',
    'MI': 'Misc',
    'U': 'Unnamed',
    'LB': 'Fabrication Lab',
}


def _escape_xml(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def map_space_to_category(name):
    if not name:
        return 'U'
    n = name.lower()
    # Labs and fabrication
    if any(k in n for k in ('lab', 'fabrication', 'workshop', 'makerspace')):
        return 'LB'
    if any(k in n for k in ('office', 'offices')):
        return 'O'
    if any(k in n for k in ('student', 'study', 'tutorial')):
        return 'SD'
    if any(k in n for k in ('meeting', 'conference', 'boardroom', 'huddle', 'seminar')):
        return 'MR'
    if any(k in n for k in ('cafe', 'kitchen', 'dining', 'canteen', 'coffee', 'restaurant')):
        return 'C'
    if any(k in n for k in ('multi', 'multipurpose')):
        return 'MP'
    if any(k in n for k in ('auditorium', 'auditor')):
        return 'AU'
    if 'atrium' in n:
        return 'AT'
    if 'library' in n:
        return 'L'
    if any(k in n for k in ('entrance', 'lobby', 'reception', 'foyer')):
        return 'E'
    if any(k in n for k in ('wc', 'toilet', 'restroom', 'shower', 'bath', 'changing', 'janitor', 'vestibule')):
        return 'W'
    if any(k in n for k in ('stair', 'lift', 'elevator')):
        return 'V'
    if any(k in n for k in ('hall', 'corridor', 'corridors', 'hallway')):
        return 'H'
    if any(k in n for k in ('mechanical', 'sprinkler', 'electrical', 'mep', 'ahu', 'service', 'heating', 'server', 'transformer')):
        return 'T'
    if 'shaft' in n:
        return 'S'
    if 'roof' in n:
        return 'RF'
    if any(k in n for k in ('garden', 'green')):
        return 'G'
    if any(k in n for k in ('store', 'storage', 'storeroom')):
        return 'ST'
    if any(k in n for k in ('bike', 'bicycle')):
        return 'B'
    if any(k in n for k in ('misc',)):
        return 'MI'
    # fallback
    return 'MI'


def make_svgs(grid_data, out_dir=None, grid_json_path=None):
    if out_dir is None:
        # if the grid JSON path is provided, write svg output into a sibling 'svg' folder
        if grid_json_path:
            out_dir = os.path.join(os.path.dirname(grid_json_path), 'svg')
        else:
            out_dir = os.path.join(ROOT, 'gridViz_out')
    os.makedirs(out_dir, exist_ok=True)
    colors = load_colors()

    for floor_key, floor in grid_data.items():
        # collect all centroids to compute bounds
        centroids = []
        entries = []
        for grid in floor.get('grids', []):
            for sq in grid.get('squares', []):
                i = sq.get('i')
                j = sq.get('j')
                cx, cy, cz = sq.get('centroid', [0, 0, 0])
                # Prefer explicit 'assigned_space_name' key from grid_spaces.json but fall back to common alternatives
                assigned_name = sq.get('assigned_space_name') or sq.get('assigned_name') or sq.get('assignedSpaceName') or sq.get('assigned_space') or sq.get('name')
                entries.append({'i': i, 'j': j, 'cx': cx, 'cy': cy, 'name': assigned_name})
                centroids.append((cx, cy))
        if not entries:
            continue
        xs = sorted(set(e['cx'] for e in entries))
        ys = sorted(set(e['cy'] for e in entries))
        # compute typical cell size as median diff
        dxs = [xs[k+1]-xs[k] for k in range(len(xs)-1)] if len(xs) > 1 else [1000]
        dys = [ys[k+1]-ys[k] for k in range(len(ys)-1)] if len(ys) > 1 else [1000]
        cell_w = abs(statistics.median(dxs))
        cell_h = abs(statistics.median(dys))

        minx = min(c[0] for c in centroids) - cell_w/2.0
        maxx = max(c[0] for c in centroids) + cell_w/2.0
        miny = min(c[1] for c in centroids) - cell_h/2.0
        maxy = max(c[1] for c in centroids) + cell_h/2.0

        # target canvas size
        target_w = 1200
        target_h = 1000
        model_w = maxx - minx
        model_h = maxy - miny if maxy > miny else 1
        scale = min(target_w / model_w if model_w>0 else target_w, target_h / model_h if model_h>0 else target_h)
        pad = 10
        svg_w = int(model_w * scale + pad*2)
        svg_h = int(model_h * scale + pad*2 + 120)  # room for legend

        # build rects
        rects = []
        for e in entries:
            # map model coords to svg
            x_model = e['cx'] - cell_w/2.0
            y_model = e['cy'] - cell_h/2.0
            # SVG x: offset from minx
            x_svg = (x_model - minx) * scale + pad
            # SVG y: invert so larger model y is up
            y_svg = (maxy - (e['cy'] + cell_h/2.0)) * scale + pad
            w_svg = cell_w * scale
            h_svg = cell_h * scale
            cat = map_space_to_category(e.get('name'))
            color = colors.get(cat, '#cccccc')
            rects.append({'x': x_svg, 'y': y_svg, 'w': w_svg, 'h': h_svg, 'color': color, 'cat': cat, 'name': e.get('name')})

        # svg content
        parts = []
        parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">')
        parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
        # draw squares with centered category abbreviation labels and hover titles
        for r in rects:
            label = (r.get('cat') or '').upper()
            name = r.get('name') or ''
            title_text = (name if name else label).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            text_color = _label_contrast(r.get('color', '#cccccc'))
            # font size scaled to cell
            font_size = max(8, min(18, int(min(r['w'], r['h']) / 3)))
            cx = r['x'] + r['w'] / 2.0
            cy = r['y'] + r['h'] / 2.0
            parts.append(f'<g>')
            parts.append(f'<title>{title_text}</title>')
            parts.append(f'<rect x="{r["x"]:.2f}" y="{r["y"]:.2f}" width="{r["w"]:.2f}" height="{r["h"]:.2f}" fill="{r["color"]}" stroke="#444" stroke-width="0.5"/>')
            parts.append(f'<text x="{cx:.2f}" y="{cy:.2f}" fill="{text_color}" font-family="Arial" font-size="{font_size}" text-anchor="middle" dominant-baseline="middle">{label}</text>')
            parts.append(f'</g>')
        # legend
        legend_x = pad
        legend_y = svg_h - 110
        parts.append(f'<g font-family="Arial" font-size="12">')
        parts.append(f'<text x="{legend_x}" y="{legend_y - 6}" fill="#000">Floor: {floor_key}</text>')
        lx = legend_x
        ly = legend_y + 10
        # unique categories in this floor
        cats = []
        for r in rects:
            if r['cat'] not in cats:
                cats.append(r['cat'])
        for idx, c in enumerate(sorted(cats)):
            col = colors.get(c, '#cccccc')
            cx = lx + (idx % 6) * 180
            cy = ly + (idx // 6) * 20
            # build display text: include full name in brackets (shorten if long)
            full = CATEGORY_NAMES.get(c, c)
            disp = full if len(full) <= 28 else full[:25] + '...'
            display_text = f"{c} ({disp})"
            display_text = _escape_xml(display_text)
            parts.append(f'<rect x="{cx}" y="{cy - 12}" width="16" height="12" fill="{col}" stroke="#000"/>')
            parts.append(f'<text x="{cx + 22}" y="{cy - 2}" fill="#000">{display_text}</text>')
        parts.append('</g>')
        parts.append('</svg>')

        svg_path = os.path.join(out_dir, f'{floor_key}.svg')
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(parts))
        print('Wrote', svg_path)


if __name__ == '__main__':
    grid_path = None
    building = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isdir(arg) or os.path.isfile(arg):
            grid_path = arg
        else:
            building = arg
    data, path = load_grid(path=grid_path, building=building)
    make_svgs(data, grid_json_path=path)
