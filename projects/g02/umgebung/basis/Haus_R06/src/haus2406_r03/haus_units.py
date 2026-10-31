# -*- coding: utf-8 -*-
"""Unit contract only; no NX import, geometry changes or unit conversion.

PartCollection.NewDisplay takes Part.Units. BasePart.PartUnits returns
BasePart.Units. Those are separate enum families, even when names match.
Runtime values are logged, but repr/strings/numbers are NEVER used to accept
an otherwise mismatched unit. A real NX execution is still required.
"""


class UnitCheckError(RuntimeError):
    """Carries JSON-safe information into the journal start-error report."""

    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.nx_unit_check = diagnostic


def describe_value(value):
    cls = type(value)
    label = cls.__module__ + '.' + cls.__qualname__
    try:
        text = repr(value)
    except Exception as error:
        # A faulty representation must not hide the underlying unit problem.
        text = '<repr failed: ' + type(error).__name__ + '>'
    return {'type': label, 'repr': text}


def verify_millimeters(part, nx_module, ident):
    """Read-only, exact BasePart.Units check with explicit unknown-type handling."""
    diagnostic = {
        'context': str(ident),
        'api_property': 'NXOpen.BasePart.PartUnits',
        'expected_symbol': 'NXOpen.BasePart.Units.Millimeters',
        'status': 'ABFRAGE_LAEUFT',
        'conversion_performed': False,
    }
    try:
        expected = nx_module.BasePart.Units.Millimeters
        diagnostic['expected'] = describe_value(expected)
        actual = part.PartUnits
        diagnostic['actual'] = describe_value(actual)
    except Exception as error:
        diagnostic['status'] = 'ABFRAGE_FEHLGESCHLAGEN'
        diagnostic['query_error'] = type(error).__name__ + ': ' + str(error)
        raise UnitCheckError(
            'PartUnits-Abfrage fehlgeschlagen fuer ' + str(ident) + ': ' +
            diagnostic['query_error'] + '. Keine automatische Einheitenumrechnung.',
            diagnostic) from error

    # Do not accept bool/int/string values merely because they can be coerced
    # to the ordinal or label of an enum member. No guessed UF fallback.
    if not isinstance(actual, type(expected)):
        diagnostic['status'] = 'UNERWARTETER_RUECKGABETYP'
        raise UnitCheckError(
            'PartUnits-Rueckgabetyp unerwartet fuer ' + str(ident) +
            ': Ist=' + diagnostic['actual']['repr'] +
            ' [' + diagnostic['actual']['type'] + ']; Soll=' +
            diagnostic['expected_symbol'] + ' [' + diagnostic['expected']['type'] +
            ']. Keine automatische Einheitenumrechnung.', diagnostic)
    try:
        matches = actual == expected
    except Exception as error:
        diagnostic['status'] = 'VERGLEICH_FEHLGESCHLAGEN'
        diagnostic['comparison_error'] = type(error).__name__ + ': ' + str(error)
        raise UnitCheckError('PartUnits-Vergleich fehlgeschlagen fuer ' + str(ident) +
                             ': ' + diagnostic['comparison_error'], diagnostic) from error
    if not matches:
        diagnostic['status'] = 'NICHT_MILLIMETER'
        raise UnitCheckError(
            'Part ist nicht in Millimetern: ' + str(ident) +
            '; Ist=' + diagnostic['actual']['repr'] +
            ' [' + diagnostic['actual']['type'] + ']; Soll=' +
            diagnostic['expected_symbol'] +
            '. Lauf gestoppt; keine automatische Einheitenumrechnung.', diagnostic)
    diagnostic['status'] = 'MILLIMETER_BESTAETIGT'
    return diagnostic
