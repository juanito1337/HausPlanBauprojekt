# -*- coding: utf-8 -*-
"""Parameter provenance stored on the owning PART, never on NX expressions.

Pure standard-library encoding. These records are build-time provenance, not
live NX expression values. ASCII JSON chunks avoid a single long attribute.
No fallback discards failed writes; mandatory metadata errors stop the run.
"""
import hashlib
import json
import re

SCHEMA = 'HAUS_PARAMETER_METADATA_V1'
CHUNK_CHARS = 100  # Internal conservative limit, NOT a claimed NX API limit.

OBJECT_ATTRIBUTE_SCHEMA = 'HAUS_OBJECT_ATTRIBUTES_V2'
ATTRIBUTE_NAMESPACE = 'HAUS_'
# Old titles are only labels in this mapping. Never write them to NX.
OBJECT_ATTRIBUTE_TITLES = {
    'HAUS_ID': 'HAUS_ID',
    'QUELLSTATUS': 'HAUS_QUELLSTATUS',
    'BAUZUSTAND': 'HAUS_BAUZUSTAND',
    'QUELLE': 'HAUS_QUELLE',
    'MODELLART': 'HAUS_MODELLART',
    'GENAUIGKEIT': 'HAUS_GENAUIGKEIT',
    'REVISION': 'HAUS_REVISION',
    'ELTERN_ID': 'HAUS_ELTERN_ID',
    'WIRTSWAND': 'HAUS_WIRTSWAND',
    'KATEGORIE': 'HAUS_KATEGORIE',
    'MATERIAL': 'HAUS_MATERIAL',
    'DETAILHERKUNFT': 'HAUS_DETAILHERKUNFT',
}


def validate_project_attribute_title(title):
    """Project policy, NOT a list of every NX-reserved attribute name.

    Only our explicit namespace is writable. No auto-renaming in this low-level
    function: invalid callers fail before entering NX and must be corrected.
    Mixed case is needed for existing, case-sensitive parameter identifiers.
    """
    if not isinstance(title, str) or not re.fullmatch(r'HAUS_[A-Za-z0-9_]+', title):
        raise ValueError('Attributname ausserhalb des Projekt-Namensraums HAUS_: ' + safe_text(title))
    return title


def object_attributes(meta):
    """Encode unchanged element metadata under project-owned attribute titles.

    HAUS_MATERIAL is source text only. This does not assign an NX physical
    material or density, and does not unlock/delete/write NX's MATERIAL field.
    Empty/unknown values remain empty; we do not invent a construction material.
    """
    if not isinstance(meta, dict):
        raise TypeError('Bauteil-Metadaten muessen ein Objekt sein.')
    sources = '; '.join('%s S.%s %s' % (s.get('document', '?'), s.get('page', '?'), s.get('location', ''))
                        for s in meta.get('sources', []))
    values = {'HAUS_ID': meta.get('id', ''), 'QUELLSTATUS': meta.get('status', ''),
              'BAUZUSTAND': meta.get('phase', 'UNGEKLAERT'), 'QUELLE': sources,
              'MODELLART': 'NX_GEOMETRIE_KEIN_NATIVES_BIM',
              'GENAUIGKEIT': 'PRUEFMODELL_NICHT_AUSFUEHRUNGSREIF', 'REVISION': meta.get('revision','R06'),
              'ELTERN_ID': meta.get('parent_id', ''), 'WIRTSWAND': meta.get('host_wall', ''),
              'KATEGORIE': meta.get('category', meta.get('kind', '')), 'MATERIAL': meta.get('material', ''),
              'DETAILHERKUNFT': meta.get('detail_origin', 'PLANREKONSTRUKTION_MIT_NAEHERUNGEN')}
    result = {}
    for old_title, value in values.items():
        title = validate_project_attribute_title(OBJECT_ATTRIBUTE_TITLES[old_title])
        if title in result:
            raise ValueError('Doppelte Projekt-Attributzuordnung: ' + title)
        result[title] = value
    extra = {
        'HAUS_TIEFENBELEG': meta.get('depth_evidence_status'),
        'HAUS_VERLEGEBAUWEISE': meta.get('depth_installation_method'),
        'HAUS_TIEFENPRUEFUNG': meta.get('depth_review_source'),
        'HAUS_TIEFENREGEL_ANWENDUNG': meta.get('depth_rule_application'),
        'HAUS_TIEFENHINWEIS': meta.get('depth_general_notice'),
        'HAUS_VIDEO_BELEG': meta.get('video_evidence'),
        'HAUS_VIDEO_SICHTBAR': meta.get('video_presence'),
        'HAUS_VIDEO_MASSSTATUS': meta.get('video_dimensions'),
        'HAUS_VIDEO_ROLLE': meta.get('video_role'),
        'HAUS_TRAGSYSTEM': meta.get('system_id'),
        'HAUS_KONSTRUKTIONSSTATUS': meta.get('construction_status'),
        'HAUS_TRAGENDE_FUNKTION': meta.get('load_bearing_status'),
        'HAUS_BESTAND_BESTAETIGT': meta.get('as_built_verified'),
        'HAUS_SCHICHT': meta.get('layer_id'),
        'HAUS_SCHICHTDICKE_MM': meta.get('layer_thickness_mm'),
        'HAUS_QUELLENVARIANTE': meta.get('source_variant'),
        'HAUS_ANSCHLUSSSTATUS': meta.get('junction_status'),
        'HAUS_DARSTELLUNG': meta.get('representation'),
        'HAUS_NETZ': meta.get('network'),
        'HAUS_HOEHENSTATUS': meta.get('vertical_status'),
        'HAUS_PLAN_DATUM': meta.get('source_date'),
        'HAUS_PLAN_GUELTIG_BIS': meta.get('valid_until'),
        'HAUS_ZEICHENEBENE_Z_MM': meta.get('display_plane_z_mm'),
        'HAUS_PLAN_BESCHRIFTUNG': meta.get('source_label'),
        'HAUS_MENGENERMITTLUNG_AUSGESCHLOSSEN': meta.get('quantity_excluded'),
        'HAUS_TECHNISCHE_KONSISTENZ_BESTAETIGT': meta.get('technical_consistency_confirmed'),
        'HAUS_DOKUMENTINHALTE_VOLLSTAENDIG': meta.get('document_coverage_complete'),
        'HAUS_QUELLENFAKT_IDS': meta.get('source_fact_ids'),
    }
    for title,value in extra.items():
        if value is not None:result[validate_project_attribute_title(title)] = str(value)
    return result


class AttributeWriteError(RuntimeError):
    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.nx_attribute_check = diagnostic


def safe_text(value):
    try:
        return str(value)
    except Exception:
        return '<NICHT_DARSTELLBAR>'


def safe_member(obj, name, default=None):
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    if value is None or type(value) in (str, int, float, bool):
        return value
    return safe_text(value)


def attribute_diagnostic(obj, key, value, exception, operation):
    kind = type(obj)
    try:
        owner = obj.OwningPart
    except Exception:
        owner = None
    return {
        'operation': safe_text(operation),
        'object_type': kind.__module__ + '.' + kind.__name__,
        'object_name': safe_member(obj, 'Name', '<UNBEKANNT>'),
        'object_tag': safe_member(obj, 'Tag'),
        'part_file': safe_member(owner, 'FullPath'),
        'attribute': safe_text(key),
        'value_chars': len(value),
        'nx_error_code': safe_member(exception, 'ErrorCode'),
        'error': safe_text(exception),
        'policy': 'FEHLER_STOPPT_LAUF_KEIN_STILLES_WEGLASSEN',
    }


def parameter_attributes(name, item):
    """Return collision-free part attributes with lossless provenance JSON.

    No NX calls. Validate/serialize BEFORE creating the expression. Bound the
    parameter ID instead of silently truncating or normalizing it.
    """
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name):
        raise ValueError('Parameter-ID fuer Part-Metadaten ungueltig: ' + safe_text(name))
    if not isinstance(item, dict):
        raise ValueError('Parameter-Metadaten muessen ein Objekt sein: ' + name)
    if not isinstance(item.get('status'), str) or not item['status'] or len(item['status']) > 100:
        raise ValueError('Parameter-Quellstatus ungueltig: ' + name)
    if item.get('unit') not in ('mm', 'deg'):
        raise ValueError('Parameter-Einheit ungueltig: ' + name)
    payload = {'schema': SCHEMA, 'expression_name': name, 'definition_at_build': item}
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)
    chunks = [text[i:i+CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]
    if len(chunks) > 9999:
        raise ValueError('Parameter-Metadaten zu gross: ' + name)
    prefix = 'HAUS_PARAM_' + name + '__'
    values = {
        prefix+'STATUS': item['status'],
        prefix+'EINHEIT': item['unit'],
        prefix+'JSON_N': str(len(chunks)),
        prefix+'SHA256': hashlib.sha256(text.encode('ascii')).hexdigest(),
    }
    for index, chunk in enumerate(chunks, 1):
        values[prefix+'JSON_%04d' % index] = chunk
    # COMMIT marker is written last. Failures before it cannot look complete.
    values[prefix+'FORMAT'] = SCHEMA
    return values, json.loads(text)


def decode_parameter_attributes(name, attributes):
    """Offline integrity check for a mapping; no unverified NX read method."""
    prefix = 'HAUS_PARAM_' + name + '__'
    if attributes[prefix+'FORMAT'] != SCHEMA:
        raise ValueError('Metadatenformat ungueltig: ' + name)
    count = int(attributes[prefix+'JSON_N'])
    if not 1 <= count <= 9999:
        raise ValueError('Ungueltige Metadaten-Teilzahl: ' + name)
    text = ''.join(attributes[prefix+'JSON_%04d' % i] for i in range(1, count+1))
    digest = hashlib.sha256(text.encode('ascii')).hexdigest()
    if digest != attributes[prefix+'SHA256']:
        raise ValueError('Parameter-Metadatenpruefsumme falsch: ' + name)
    data = json.loads(text)
    if data['schema'] != SCHEMA or data['expression_name'] != name:
        raise ValueError('Parameter-Metadaten falsch zugeordnet: ' + name)
    if data['definition_at_build']['status'] != attributes[prefix+'STATUS']:
        raise ValueError('Parameter-Quellstatus widerspruechlich: ' + name)
    if data['definition_at_build']['unit'] != attributes[prefix+'EINHEIT']:
        raise ValueError('Parameter-Einheit widerspruechlich: ' + name)
    return data
