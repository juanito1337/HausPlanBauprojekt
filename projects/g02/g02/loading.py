# -*- coding: utf-8 -*-
"""H01a: load existing NX parts before metadata/geometry/assembly queries.

No Save/Close/SetDisplay/SetWork calls; no global LoadOptions changes.
The load-state flag is re-read after every request. A missing status object is
recorded as missing (not as a zero error count); actual IsFullyLoaded must still
be True. Reported failures, even with a True flag, stop the operation.
"""
import time
from . import height_model as model


class PartLoadingError(RuntimeError):
    pass


def _boolean(value, label):
    if callable(value):
        value = value()
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise PartLoadingError(label + ': eindeutiger boolescher Ladestatus fehlt.')


def _error(error):
    out = {'message': str(error), 'type': type(error).__name__}
    try:
        code = getattr(error, 'ErrorCode', None)
        if code is not None:
            out['nx_error_code'] = int(code)
    except Exception:
        pass  # error-report enrichment only; never used to decide success
    return out


def part_identity(part):
    """Best-effort diagnostic identity, no deep NX object access."""
    out = {'path': None, 'tag': None}
    if part is None:
        return out
    for field, attr in (('path', 'FullPath'), ('tag', 'Tag')):
        try:
            value = getattr(part, attr)
            out[field] = int(value) if field == 'tag' else str(value)
        except Exception as error:
            out[field + '_read_error'] = _error(error)
    return out


class PartLoader:
    def __init__(self, session, state, record_event):
        self.session = session
        self.record_event = record_event
        self.state = state.setdefault('part_loading', {
            'policy': 'EXISTING_PROJECT_PARTS_ONLY_BEFORE_READ',
            'calls': [], 'verified_parts': {}, 'state_checks': 0,
            'global_load_options_changed': False,
            'source_files_saved': False, 'parts_closed': False,
            'session_load_state_may_change': True,
        })
        self.subtree_attempted = set()

    def _flag(self, part):
        self.state['state_checks'] += 1
        try:
            return _boolean(part.IsFullyLoaded, 'BasePart.IsFullyLoaded')
        except Exception as error:
            self.record_event({'event': 'LOAD_STATE_READ_FAILED',
                               'part': part_identity(part), 'error': _error(error)})
            raise PartLoadingError('NX-Ladestatus nicht lesbar: ' +
                                   str(part_identity(part)) + '. ' + str(error)) from error

    def _load_status(self, status, entry):
        """Read every reported failure and always release the returned status."""
        entry['status_object_returned'] = status is not None
        entry['number_unloaded_parts'] = None
        entry['unloaded_parts'] = []
        entry['status_disposed'] = None
        if status is None:
            # Some successful no-op bindings can expose a null status. We do not
            # infer success here; the caller independently verifies IsFullyLoaded.
            return
        failure = None
        try:
            count = status.NumberUnloadedParts
            if callable(count):
                count = count()
            if type(count) is not int or not 0 <= count <= 10000:
                raise PartLoadingError('NX-Ladestatus: ungueltige NumberUnloadedParts.')
            entry['number_unloaded_parts'] = count
            for index in range(count):
                row = {'index': index}
                for key, method in (('part_name', 'GetPartName'),
                                    ('code', 'GetStatus'),
                                    ('description', 'GetStatusDescription')):
                    try:
                        value = getattr(status, method)(index)
                        row[key] = int(value) if key == 'code' else str(value)
                    except Exception as error:
                        row[key + '_read_error'] = _error(error)
                entry['unloaded_parts'].append(row)
            if count:
                raise PartLoadingError('NX meldet ' + str(count) +
                    ' nicht vollstaendig geladene Teile: ' +
                    '; '.join(row.get('part_name', '?') + ': ' +
                    row.get('description', 'Details im Protokoll')
                    for row in entry['unloaded_parts']))
        except Exception as error:
            failure = error
        finally:
            try:
                status.Dispose()
                entry['status_disposed'] = True
            except Exception as error:
                entry['status_disposed'] = False
                entry['dispose_error'] = _error(error)
                if failure is None:
                    failure = PartLoadingError('NX-Ladestatus nicht freigegeben: ' + str(error))
        if failure is not None:
            raise failure

    def _request(self, part, method, include_children, action, context):
        entry = {'part': part_identity(part), 'context': context,
                 'method': method, 'include_children': include_children,
                 'before_fully_loaded': self._flag(part),
                 'after_fully_loaded': None, 'status': 'REQUESTED'}
        self.state['calls'].append(entry)
        self.record_event({'event': 'FULL_LOAD_BEGIN', 'request': entry})
        start = time.perf_counter()
        before_file = None
        try:
            # No file/path invention: an existing source must be accessible.
            if not entry['part']['path']:
                raise PartLoadingError('Part hat keinen lesbaren Quelldateipfad.')
            before_file = model.file_record(entry['part']['path'])
            entry['source_file_before'] = before_file
            status = action()
            self._load_status(status, entry)
            entry['after_fully_loaded'] = self._flag(part)
            if entry['after_fully_loaded'] is not True:
                raise PartLoadingError('Part bleibt nach dem Ladeaufruf nur teilweise geladen: ' +
                                       entry['part']['path'])
            model.verify_records([before_file])
            entry['source_file_unchanged'] = True
            entry['status'] = 'FULLY_LOADED_FLAG_CONFIRMED'
        except Exception as error:
            entry['status'] = 'FAILED'
            entry['error'] = _error(error)
            if entry['after_fully_loaded'] is None:
                try:
                    entry['after_fully_loaded'] = self._flag(part)
                except Exception as flag_error:
                    entry['after_flag_error'] = _error(flag_error)
            raise PartLoadingError('Vollstaendiges Nachladen fehlgeschlagen (' + method +
                                   '): ' + str(entry['part']['path']) + '\n' + str(error)) from error
        finally:
            entry['seconds'] = time.perf_counter() - start
            self.record_event({'event': 'FULL_LOAD_END', 'request': entry})

    def ensure_part(self, part, context):
        if part is None:
            raise PartLoadingError('Kein geladener Komponentenprototyp: ' + context)
        before = self._flag(part)
        if not before:
            # Prefer the narrowly scoped method. Never promote all open session
            # parts or change the user's saved/global load settings.
            action = getattr(part, 'LoadThisPartFully', None)
            if callable(action):
                self._request(part, 'BasePart.LoadThisPartFully', False, action, context)
            else:
                method = getattr(self.session.Parts, 'EnsurePartsLoadedFully', None)
                if not callable(method):
                    raise PartLoadingError('Kein unterstuetzter NX-Volladeaufruf verfuegbar: ' + context)
                self._request(part, 'PartCollection.EnsurePartsLoadedFully', False,
                              lambda: method([part], False), context)
        identity = part_identity(part)
        self.state['verified_parts'][str(identity['tag'])] = dict(identity, fully_loaded=True)
        self.record_event({'event': 'PART_READY_FOR_READ', 'part': identity,
                           'already_fully_loaded': before, 'context': context})
        return part

    def children(self, part, context):
        """Load parent first. Resolve null prototypes once through its own tree.

        No manual pathname reconstruction, no substitution with another open
        part of the same name, and no suppression/reference-set changes.
        """
        self.ensure_part(part, context)
        root = part.ComponentAssembly.RootComponent
        if root is None:
            return []
        children = list(root.GetChildren())
        missing = [c for c in children if c.Prototype is None]
        if missing:
            key = int(part.Tag)
            method = getattr(self.session.Parts, 'EnsurePartsLoadedFully', None)
            if key in self.subtree_attempted or not callable(method):
                raise PartLoadingError('Unterkomponente ohne geladenen Prototyp; keine geratenen Dateipfade: ' + context)
            self.subtree_attempted.add(key)
            self._request(part, 'PartCollection.EnsurePartsLoadedFully', True,
                          lambda: method([part], True), context + ' / fehlende Unterteile')
            root = part.ComponentAssembly.RootComponent
            if root is None:
                raise PartLoadingError('Baugruppenwurzel nach Nachladen verschwunden: ' + context)
            children = list(root.GetChildren())
            missing = [c for c in children if c.Prototype is None]
            if missing:
                names = []
                for component in missing:
                    try:
                        names.append(str(component.Name))
                    except Exception:
                        names.append('<Name nicht lesbar>')
                raise PartLoadingError('Unterkomponenten bleiben ungeladen: ' + ', '.join(names))
        return children
