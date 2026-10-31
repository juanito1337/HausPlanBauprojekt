"""Integrity and ZIP helpers. Standard library only; never touches NX."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Iterable, Mapping
import zipfile


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def member_path(root: Path, name: str) -> Path:
    """Accept only relative, portable POSIX names, without symlink traversal."""
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\0' in name:
        raise ValueError('Invalid relative filename: ' + repr(name))
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('.', '..', '') for p in name.split('/')):
        raise ValueError('Path traversal or non-canonical filename: ' + name)
    result = Path(root).absolute()
    if result.is_symlink():
        raise ValueError('Root must not be a symlink')
    for part in path.parts:
        result = result / part
        if result.is_symlink():
            raise ValueError('Symlink not accepted: ' + name)
    return result


def _unique_names(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for name in names:
        key = name.casefold()
        if key in seen:
            raise ValueError('Duplicate/case-colliding filename: ' + name)
        seen.add(key)
        result.append(name)
    return sorted(result)


def check_files(root: Path, expected: Mapping[str, str]) -> list[dict[str, str]]:
    errors = []
    for name in _unique_names(expected):
        wanted = expected[name]
        if not isinstance(wanted, str) or re.fullmatch('[0-9a-f]{64}', wanted) is None:
            raise ValueError('Invalid SHA-256 for ' + name)
        path = member_path(root, name)
        if not path.is_file():
            errors.append({'file': name, 'kind': 'missing'})
            continue
        actual = digest(path)
        if actual != wanted:
            errors.append({'file': name, 'kind': 'changed', 'expected': wanted, 'actual': actual})
    return errors


def check_python_syntax(root: Path, names: Iterable[str]) -> list[dict[str, str]]:
    errors = []
    for name in names:
        if not name.endswith('.py'):
            continue
        try:
            path = member_path(root, name)
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=name, feature_version=(3, 10))
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors.append({'file': name, 'error': str(exc)})
    return errors


def build_archive(root: Path, names: Iterable[str], output: Path, prefix: str) -> dict:
    """Build an exclusive ZIP outside root; verify every archived payload before release."""
    root = Path(root).absolute()
    output = Path(output).absolute()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(root):
        raise ValueError('ZIP must be outside repository')
    if len(PurePosixPath(prefix).parts) != 1:
        raise ValueError('Prefix must be a single folder')
    member_path(root, prefix)
    selected = _unique_names(names)
    checked = []
    for name in selected:
        if '.git' in PurePosixPath(name).parts:
            raise ValueError('Do not package .git metadata')
        path = member_path(root, name)
        if not path.is_file():
            raise FileNotFoundError(path)
        checked.append((name, path, digest(path)))
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='.hausplan_', suffix='.zip.tmp', dir=output.parent)
    os.close(fd)
    temp = Path(tmp_name)
    created_output = False
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, path, _ in checked:
                archive.write(path, prefix + '/' + name)
        with zipfile.ZipFile(temp) as archive:
            failure = archive.testzip()
            if failure:
                raise ValueError('ZIP CRC failed: ' + failure)
            for name, _, wanted in checked:
                with archive.open(prefix + '/' + name) as stream:
                    h = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(block)
                if h.hexdigest() != wanted:
                    raise ValueError('File changed during packaging: ' + name)
        # Exclusive target creation prevents an accidental overwrite of another delivery.
        with output.open('xb') as target, temp.open('rb') as source:
            created_output = True
            shutil.copyfileobj(source, target, length=1024 * 1024)
        return {'archive': output.name, 'files': len(checked), 'bytes': output.stat().st_size,
                'sha256': digest(output), 'crc_passed': True, 'all_payload_hashes_passed': True,
                'NX_run_performed': False}
    except Exception:
        if created_output:
            output.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)


def extract_json_assignment(text: str) -> dict:
    """Read K01's literal `const P = <JSON>;` as data, NEVER execute JavaScript."""
    matches = list(re.finditer(r"\bconst\s+P\s*=\s*", text))
    if len(matches) != 1:
        raise ValueError('Exactly one const P JSON assignment required')
    tail = text[matches[0].end():]
    value, end = json.JSONDecoder().raw_decode(tail)
    if not isinstance(value, dict) or not tail[end:].lstrip().startswith(';'):
        raise ValueError('Expected a JSON object terminated by a semicolon')
    return value
