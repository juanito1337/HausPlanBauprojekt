# -*- coding: utf-8 -*-
"""R09a: geprüfte Dokumenthinweise, KEINE Ableitung einer realen Leitungstiefe.

Weder Mittelwert einer Regeltiefenspanne noch DGM-Höhe noch planare Maßzahl
werden in die z_mm-Werte der Trassen geschrieben. Keine neuen NX-API-Aufrufe.
"""
import copy
import math
from .core import read_json, sha256, within

REVIEW_FILE = 'data/LEITUNGSTIEFEN_PRUEFUNG_R09a.json'


def validate_review(review, data):
    if review.get('schema') != 'R09A_UTILITY_DEPTH_REVIEW_V1':
        raise ValueError('Unbekanntes Leitungsprüfregister.')
    docs = review.get('documents', [])
    ids = [d['document'] for d in docs]
    if len(ids) != len(set(ids)) or len(docs) != review.get('document_count'):
        raise ValueError('Doppelte/unvollständige Leitungsquellen.')
    if sum(d['pages'] for d in docs) != review.get('page_count'):
        raise ValueError('Seitenzahl des Leitungsprüfregisters widersprüchlich.')
    source_pages = data['source_document_pages']
    for d in docs:
        if type(d['pages']) is not int or d['pages'] != source_pages.get(d['document']):
            raise ValueError('Quellseitenzahl passt nicht zum Hausregister: '+d['document'])
    rule_ids = set()
    for rule in review.get('rules', []):
        if rule['id'] in rule_ids:
            raise ValueError('Doppelte Regel-ID.')
        rule_ids.add(rule['id'])
        s = rule['source']
        if s['document'] not in ids or not 1 <= s['page'] <= source_pages[s['document']]:
            raise ValueError('Regelquelle/Seite unbekannt.')
        if rule.get('applied_to_routes') is not False or rule.get('as_built_verified') is not False:
            raise ValueError('Allgemeine Regel darf nicht als Isttiefe freigegeben sein.')
        if rule.get('is_safe_depth_envelope') is not False:
            raise ValueError('Regelspanne ist kein sicherer Tiefenkorridor.')
        lo, hi = rule.get('cover_min_m'), rule.get('cover_max_m')
        for x in (lo, hi):
            if x is not None and (type(x) not in (int, float) or not math.isfinite(x) or x < 0):
                raise ValueError('Ungültige allgemeine Überdeckung.')
        if lo is not None and hi is not None and lo > hi:
            raise ValueError('Vertauschte Regelbereichsgrenzen.')
    routes = {r['id']: r for r in data['site']['routes']}
    rows = review.get('routes', [])
    if len(rows) != len(routes) or {r['route_id'] for r in rows} != set(routes):
        raise ValueError('Tiefenprüfung deckt nicht jede aktuelle Trasse genau einmal ab.')
    for row in rows:
        route = routes[row['route_id']]
        if row['network'] != route['network'] or row['sources'] != route['sources']:
            raise ValueError('Sparte/Quellzuordnung im Tiefenregister verändert: '+route['id'])
        if row.get('depth_m') is not None or row.get('height_mm') is not None:
            raise ValueError('Neue Isttiefe erfordert einen separaten objektbezogenen Nachweis, nicht dieses Regelregister.')
        if row.get('installation_method') is not None:
            raise ValueError('Bauweise im bereitgestellten Register nicht nachgewiesen.')
        if route.get('z_mm') is not None:
            raise ValueError('Trassenhöhen geändert: R09a-Tiefenregister ist neu abzugleichen.')
        if row.get('general_rules_assigned_as_physical_depth') is not False:
            raise ValueError('Regelhinweis darf keine physische Leitungsachse setzen.')
        refs = row.get('general_information_ids', [])
        if any(r not in rule_ids for r in refs):
            raise ValueError('Unbekannte Tiefenregel referenziert.')
        if refs and row['network'] != 'BREITBAND':
            raise ValueError('SWN-TK-Regel nicht automatisch auf Gas/Strom/Telekom übertragbar.')
    return {'documents_reviewed':len(docs), 'pages_reviewed':review['page_count'],
            'routes_reviewed':len(rows), 'general_rule_rows':len(rule_ids),
            'confirmed_route_depths':0, 'geometry_changed':False,
            'rule_values_used_as_built_depth':False, 'status':review['status']}


def load_review(base):
    review = read_json(base / REVIEW_FILE)
    data = read_json(base / 'basis/Haus_R06/data/haus.json')
    summary = validate_review(review, data)
    for item in review['documents']:
        if sha256(within(base, item['file'])) != item['sha256']:
            raise ValueError('Geprüfte Original-Leitungsquelle fehlt/verändert: '+item['file'])
    return review, summary


def decorate_house_data(data, review):
    """Neue Herkunftsattribute in der eigenen Laufkopie. Keine Geometrie ändern."""
    validate_review(review, data)
    result = copy.deepcopy(data)
    records = {r['route_id']:r for r in review['routes']}
    for route in result['site']['routes']:
        record = records[route['id']]
        route['depth_evidence_status'] = record['evidence_status']
        route['depth_installation_method'] = 'UNBEKANNT'
        route['depth_review_source'] = 'R09a: Originalprüfung G11–G19; 15 Seiten'
        route['depth_rule_application'] = 'KEINE_REGELWERTE_ALS_ISTTIEFE'
        if route['network'] == 'BREITBAND':
            route['depth_general_notice'] = ('G15 S.3 Abs.8, SWN 12.01.2018: offene Bauweise 0,30–1,50 m '
                 'Überdeckung; Bohrungen bis zu 5 m. Bauweise unbekannt. KEIN Bestandswert; kein sicherer Korridor.')
        elif route['network'] == 'STROM':
            route['depth_general_notice'] = ('G15 S.3 verweist für Strom/Gas auf SH-Netz-Merkblatt, nicht '
                 'mitgeliefert. G18-Lagemaße sind keine Tiefen. Keine numerische Tiefenzuweisung.')
        elif route['network'].startswith('GAS'):
            route['depth_general_notice'] = ('G11 VBB-Gasplan: keine eindeutig bezeichnete Tiefenangabe. '
                 'SWN-Regelbereiche werden nicht auf dieses Netz übertragen.')
        else:
            route['depth_general_notice'] = ('G19 Telekom-Plan: keine eindeutig bezeichnete Tiefenangabe. '
                 'Keine automatische Übernahme der SWN-TK-Regelwerte.')
    # Präzisierung des vorhandenen Quellenfakts, keine neue Geometrie/Tragfunktion.
    q42 = next((f for f in result.get('source_facts', []) if f['id']=='Q42'), None)
    if q42 is not None:
        q42['sources'] = [{'document':'G15','page':3,'location':'Abschnitt 8 Verlegetiefen; Regelhinweise'},
                         {'document':'G15','page':2,'location':'Abschnitte 1 und 5, Geltungsbereich/Tiefenfeststellung'}]
        q42['source_statement'] = ('SWN-Merkblatt 12.01.2018 nennt allgemeine Überdeckungen: Wasser 1,20–1,60 m; '
            'Fernwärme 0,30–1,50 m; Telekommunikation offene Bauweise 0,30–1,50 m, Bohrungen bis zu 5 m. '
            'Strom/Gas: Verweis auf SH-Netz-Merkblatt. Keine objektbezogenen Isttiefen.')
        q42['values'] = {'general_rule_records':copy.deepcopy(review['rules']), 'applied_as_route_depth':False}
        q42['remaining'] = ('Geltungsbereich und Bauweise nicht auf fremde Netze übertragen. '
            'Kein eingemessenes Tiefenprofil, kein sicherer Tiefenkorridor. Z-Werte bleiben unverändert unbekannt.')
    return result
