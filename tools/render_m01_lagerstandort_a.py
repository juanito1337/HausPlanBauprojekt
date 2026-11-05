"""Draw actual A contact polygons, without moving or generating model geometry.

Requires Pillow. A3 landscape: overview 1:250, detail 1:100 at 100% printing.
The SVG and PNG use the same coordinates, clipping and physical scale.
"""
import argparse
from html import escape
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
from renovierung.k02 import geometry as geom
from tools.check_m01_lagerstandorte import Sources, require, verify_plan, vegetation_projections


class Sheet:
    def __init__(self):
        self.image = Image.new('RGB', (4200, 2970), 'white')
        self.draw = ImageDraw.Draw(self.image)
        self.svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 4200 2970">',
                    '<rect width="4200" height="2970" fill="white"/>']

    def font(self, size, bold=False):
        path = Path('C:/Windows/Fonts')/('arialbd.ttf' if bold else 'arial.ttf')
        return ImageFont.truetype(str(path) if path.exists() else ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)

    def text(self, x, y, text, size=42, color='#233541', bold=False):
        self.draw.text((x, y), text, font=self.font(size, bold), fill=color)
        self.svg.append('<text x="%g" y="%g" font-family="Arial,sans-serif" font-size="%g" fill="%s" font-weight="%s">%s</text>' %
                        (x, y+size*.92, size, color, 'bold' if bold else 'normal', escape(text)))

    def line(self, points, color, width=3, dash=False):
        if not dash:
            self.draw.line(points, fill=color, width=width)
        else:
            for a, b in zip(points, points[1:]):
                length = math.dist(a, b)
                for offset in range(0, math.ceil(length), 30):
                    t, u = offset/length, min(offset+18, length)/length
                    self.draw.line([(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])),
                                    (a[0]+u*(b[0]-a[0]), a[1]+u*(b[1]-a[1]))], fill=color, width=width)
        self.svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%g"%s/>' %
                        (' '.join('%.3f,%.3f' % p for p in points), color, width,
                         ' stroke-dasharray="18 12"' if dash else ''))

    def polygon(self, points, fill):
        self.draw.polygon(points, fill=fill)
        self.svg.append('<polygon points="%s" fill="%s"/>' % (' '.join('%.3f,%.3f' % p for p in points), fill))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--piles', required=True, type=Path)
    parser.add_argument('--check', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='Output stem, without suffix')
    args = parser.parse_args()
    plan_raw, piles_raw, check_raw = (p.read_bytes() for p in (args.plan, args.piles, args.check))
    plan, piles, check = (json.loads(v.decode('utf-8-sig')) for v in (plan_raw, piles_raw, check_raw))
    sources = Sources(ROOT)
    data = verify_plan(sources, plan)
    for name, expected in piles['source_hashes'].items():
        sources.read(name, expected, json_data=False)
    for name, expected in check['verified_source_generator_hashes'].items():
        sources.read(name, expected, json_data=False)
    require(hashlib.sha256(plan_raw).hexdigest() == check['plan_sha256'], 'Plan differs from location check')
    require(piles['center_xy_mm'] == [14500, -9500] and piles['construction_release'] is False,
            'Expected non-released site A contact geometry')
    require(check['preferred_display_candidate'] == 'A', 'Preferred candidate differs')
    selected = next(r for r in check['candidates'] if r['id'] == 'A')
    require(selected['center_xy_mm'] == piles['center_xy_mm'] and selected['geometric_criterion_passed'] is True,
            'Site A geometric check missing')
    fields = {f['id']: f for f in plan['fields'] if f['native_candidate']}
    require(set(fields) == {f['id'] for f in piles['fields']} and len(fields) == len(piles['fields']) == 22,
            'Site A field inventory differs')
    field = fields['PS01-F01']
    active = next(f for f in piles['fields'] if f['id'] == field['id'])
    largest = max(piles['fields'], key=lambda f: f['reserve_1_25']['target_volume_m3'])
    outer = geom.convex_hull([p for poly in largest['reserve_1_25']['contact_polygons_xy_mm'] for p in poly])
    vegetation, _ = vegetation_projections(sources, 'projects/g02/umgebung/data/IMPORTAUFTRAG_R09.json', 'cad/nx/CURRENT.json')
    boundary = data['house']['site']['boundary']['points_local_mm']
    footprints = data['catalog']['footprints']
    sheet = Sheet()
    sheet.text(150, 80, 'LAGERPLATZ A · VOR DER MODELLIERTEN HECKE', 78, bold=True)
    sheet.text(153, 190, 'X = 14,500 m / Y = −9,500 m · Einzelfeld PS01-F01 · Stand 04.11.2026', 47)
    sheet.text(153, 265, 'Echte örtlich neu berechnete Kontaktpolygone · gleiche X-/Y-Skalierung · keine NX-Bildschirmaufnahme', 38, '#536570')
    sheet.text(160, 355, 'GRUNDSTÜCK  |  1:250', 45, bold=True)
    sheet.text(2050, 355, 'LAGER A UND HECKEN  |  1:100', 45, bold=True)

    def panel(name, left, top, bounds, scale, step):
        x0, y0, x1, y1 = bounds
        width, height = round((x1-x0)*scale), round((y1-y0)*scale)
        full_image, full_draw = sheet.image, sheet.draw
        tile = Image.new('RGB', (width+1, height+1), '#f7faf6')
        sheet.image, sheet.draw = tile, ImageDraw.Draw(tile)
        sheet.svg.append('<defs><clipPath id="%s"><rect x="%g" y="%g" width="%g" height="%g"/></clipPath></defs><g clip-path="url(#%s)">' %
                         (name, left, top, width, height, name))
        # Pillow uses tile-local points; SVG uses the same tile via translation.
        sheet.svg.append('<g transform="translate(%g %g)">' % (left, top))
        def xy(p): return ((p[0]-x0)*scale, (y1-p[1])*scale)
        def line(poly, color, width=3, dash=False): sheet.line([xy(p) for p in poly], color, width, dash)
        def fill(poly, color): sheet.polygon([xy(p) for p in poly], color)
        for x in range(math.ceil(x0/step)*step, int(x1)+1, step):
            line([(x, y0), (x, y1)], '#e0e7e5', 2)
        for y in range(math.ceil(y0/step)*step, int(y1)+1, step):
            line([(x0, y), (x1, y)], '#e0e7e5', 2)
        for poly in footprints.values(): fill(poly, '#dce3e7')
        for poly in footprints.values(): line(poly+[poly[0]], '#748693', 4)
        for vid, patches in vegetation.items():
            for poly in patches: fill(poly, '#3a8063')
        for f in fields.values():
            if f['id'] != field['id']:
                poly = f['uncertainty_coverage_hull']
                line(poly+[poly[0]], '#b7c1c6', 3)
        for poly in field['projection_polygons']: fill(poly, '#da7655')
        for poly in active['reserve_1_25']['contact_polygons_xy_mm']: fill(poly, '#f0d5a7')
        for poly in active['main']['contact_polygons_xy_mm']: fill(poly, '#c58c32')
        line(outer+[outer[0]], '#815a9a', 5, True)
        line(boundary+[boundary[0]], '#2e4f48', 5)
        for vid, point in {'V01': (4500, -14600), 'V02': (15700, -17500),
                           'V03': (1800, -6700), 'V05': (20100, -5400)}.items():
            p = xy(point)
            sheet.text(p[0], p[1], vid, 36, '#164d36', True)
        p = xy((14500, -9500))
        sheet.line([(p[0]-15, p[1]), (p[0]+15, p[1])], '#523d16', 4)
        sheet.line([(p[0], p[1]-15), (p[0], p[1]+15)], '#523d16', 4)
        sheet.text(p[0]+28, p[1]-20, 'A', 50, '#523d16', True)
        sheet.svg.append('</g></g>')
        sheet.image, sheet.draw = full_image, full_draw
        sheet.image.paste(tile, (left, top))
        sheet.line([(left, top), (left+width, top), (left+width, top+height),
                    (left, top+height), (left, top)], '#a3b2b6', 3)
        for x in range(math.ceil(x0/step)*step, int(x1)+1, step):
            sheet.text(left+(x-x0)*scale-18, top+height+12, '%g' % (x/1000), 31, '#536570')
        for y in range(math.ceil(y0/step)*step, int(y1)+1, step):
            sheet.text(left-100, top+(y1-y)*scale-16, '%g' % (y/1000), 31, '#536570')
        # Five model metres; unchanged under display resizing through labels.
        bx, by = left+55, top+height-95
        length = 5000*scale
        sheet.line([(bx, by), (bx+length, by)], '#233541', 8)
        sheet.line([(bx, by-12), (bx, by+12)], '#233541', 5)
        sheet.line([(bx+length, by-12), (bx+length, by+12)], '#233541', 5)
        sheet.text(bx, by-62, '5 m', 36, '#233541', True)
    panel('overview', 160, 435, (-10000, -29000, 30000, 27000), .04, 5000)
    panel('detail', 2050, 435, (7000, -19000, 23000, -3000), .10, 2000)
    sheet.text(2050, 2140, 'PS01-F01: Hauptlager 21,268 m³ · Reserve 25,319 m³, alternativ', 40, bold=True)
    legend = [('Hauptlager', '#c58c32'), ('Reserve, alternativ', '#f0d5a7'), ('Bestandshecken', '#3a8063'), ('Grube PS01-F01', '#da7655')]
    for index, (label, color) in enumerate(legend):
        x, y = 2050+(index%2)*940, 2220+(index//2)*72
        sheet.polygon([(x, y+8), (x+70, y+8), (x+70, y+43), (x, y+43)], color)
        sheet.text(x+95, y, label, 38)
    sheet.text(2050, 2400, 'Violett gestrichelt: größte Reserve-Kontakthülle aller 22 Felder.', 37, '#815a9a')
    sheet.text(2050, 2460, 'Grau: übrige Grubenhüllen, unabhängige Einzelfeldalternativen.', 37, '#536570')
    sheet.text(2050, 2540, 'Geprüfte Fehlerhülle A: Gruben ≥2,360 m · Hecken ≥0,339 m.', 39, bold=True)
    sheet.text(2050, 2605, 'Mindestens 0,60 m Grubenstreifen geometrisch eingehalten.', 39)
    sheet.text(160, 2760, 'MODELLKOORDINATEN X/Y [m] · A3 quer, 100 %: Übersicht 1:250 / Detail 1:100; Maßstabsleisten bei Größenänderung verwenden.', 37)
    sheet.text(160, 2830, 'DARSTELLUNGSKANDIDAT – KEINE AUSFÜHRUNGSFREIGABE. Zugang, Auflasten, Wurzeln und heutiger Heckenbestand ungeprüft.', 40, '#854725', True)
    sheet.text(160, 2895, 'Vegetation: bDOM 07.04.2023 / Bildmaske 12.05.2025 · Kartenrand keine Grenzvermessung · Leitungen siehe gesonderten Standortnachweis.', 33, '#536570')
    metadata = {'scope': 'OFFLINE_SOURCE_PROJECTION_NOT_NX_SCREENSHOT', 'center_xy_mm': piles['center_xy_mm'],
                'piles_sha256': hashlib.sha256(piles_raw).hexdigest(), 'plan_sha256': hashlib.sha256(plan_raw).hexdigest(),
                'location_check_sha256': hashlib.sha256(check_raw).hexdigest(),
                'renderer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'sheet_mm': [420, 297], 'overview_scale': '1:250', 'detail_scale': '1:100',
                'field': field['id'], 'largest_reserve_field': largest['id'], 'construction_release': False}
    sources.recheck()
    require(args.plan.read_bytes() == plan_raw and args.piles.read_bytes() == piles_raw and args.check.read_bytes() == check_raw,
            'Plot inputs changed during rendering')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pnginfo = PngInfo(); pnginfo.add_text('M01_SOURCE_METADATA', json.dumps(metadata, ensure_ascii=False))
    sheet.image.save(args.out.with_suffix('.png'), dpi=(254, 254), pnginfo=pnginfo)
    sheet.svg.append('<metadata>'+escape(json.dumps(metadata, ensure_ascii=False))+'</metadata></svg>')
    args.out.with_suffix('.svg').write_text('\n'.join(sheet.svg)+'\n', encoding='utf-8')
    print('PASS: actual A contact polygons; equal-axis A3 views, no NX run:', args.out)


if __name__ == '__main__':
    main()
