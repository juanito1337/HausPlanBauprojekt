"""Pure bijective logical-path / flat-delivery filename resolution."""
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
import re


def _logical(value):
    if (not isinstance(value,str) or not value or '\\' in value or ':' in value or
            PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive or
            any(not re.fullmatch(r'[A-Za-z0-9_-]+',p) for p in value.split('/')[:-1]) or
            not re.fullmatch(r'[A-Za-z0-9_-]+\.[Pp][Rr][Tt]',value.split('/')[-1])):
        raise ValueError('Unsafe logical native-part path: '+str(value))
    stem=PurePosixPath(value).stem.upper()
    if stem in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise ValueError('Reserved Windows part basename')
    return value


@lru_cache(maxsize=8)
def _checked(items):
    forward={};reverse={};logical_seen=set()
    if not items:
        raise ValueError('Empty delivery file mapping')
    for logical,basename in items:
        _logical(logical);_logical(basename)
        if '/' in basename or basename!=PurePosixPath(logical).name:
            raise ValueError('Flat delivery preserves each logical part basename')
        if logical.casefold() in logical_seen or basename.casefold() in reverse:
            raise ValueError('Casefold collision in delivery file mapping')
        logical_seen.add(logical.casefold());forward[logical]=basename;reverse[basename.casefold()]=logical
    return forward,reverse


def _mapping(file_map):
    if not isinstance(file_map,Mapping):
        raise ValueError('Delivery file_map must be a mapping')
    try:
        return _checked(tuple(sorted(file_map.items())))
    except (TypeError,AttributeError) as error:
        raise ValueError('Malformed delivery file mapping') from error


def make_file_map(layout):
    """Return unique physical basenames without modifying logical metadata.

    Multiple component occurrences may refer to the same logical Part. Distinct
    logical Parts may never share a basename, including Windows case variants.
    """
    try:
        files=[layout['master']]+[n['file'] for n in layout['nodes']]+[r['file'] for r in layout.get('review_masters',[])]
        for logical in files:_logical(logical)
        result={logical:PurePosixPath(logical).name for logical in sorted(set(files))}
        _mapping(result)
        return result
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError('Malformed logical delivery inventory') from error


def mapfile(root,logical,file_map=None):
    """Resolve a logical Part inside root; flat mode requires a bijective map."""
    root=Path(root).resolve();_logical(logical)
    if file_map is None:
        relative=logical
    else:
        forward,_=_mapping(file_map)
        if logical not in forward:raise ValueError('Unmapped logical Part: '+logical)
        relative=forward[logical]
    path=(root/relative).resolve()
    try:path.relative_to(root)
    except ValueError as error:raise ValueError('Part path escapes delivery root') from error
    if file_map is not None and path.parent!=root:
        raise ValueError('Flat delivery Part must be directly in its physical root')
    return path


def logicalfile(root,actual,file_map=None):
    """Invert an absolute native FullPath, rejecting escapes and unmapped files."""
    root=Path(root).resolve();actual=Path(actual)
    if not actual.is_absolute():raise ValueError('Native FullPath must be absolute')
    actual=actual.resolve()
    try:relative=actual.relative_to(root).as_posix()
    except ValueError as error:raise ValueError('Native FullPath escapes delivery root') from error
    if file_map is None:
        return _logical(relative)
    _,reverse=_mapping(file_map)
    if len(actual.relative_to(root).parts)!=1 or relative.casefold() not in reverse:
        raise ValueError('Native FullPath is not a mapped flat Part')
    logical=reverse[relative.casefold()]
    if mapfile(root,logical,file_map)!=actual:
        raise ValueError('Native FullPath differs from mapped physical Part')
    return logical
