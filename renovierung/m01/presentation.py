"""Deterministic M01 framing and native display settings; never save a Part.

NXOpen imports stay inside native functions. Camera fitting is pure geometry;
native setters/readback require a separate real NX pilot and reopen evidence.
"""
import math


DISPLAY_LAYERS = (101, 102, 103, 104, 200, 201, 210)
MATRIX_KEYS = ('Xx', 'Xy', 'Xz', 'Yx', 'Yy', 'Yz', 'Zx', 'Zy', 'Zz')
VIRTUAL_VIEW_MM = 140.0


def _numbers(values, count):
    if (not isinstance(values, (list, tuple)) or len(values) != count
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
        raise ValueError('Expected %s finite numeric coordinates' % count)
    return [float(v) for v in values]


def camera_spec(boundary_xyz):
    """Fit XYZ points and their complete bounding box into a 140 mm virtual view.

    origin_mm is an ABSOLUTE model-space point. Matrix rows are orthonormal
    screen-right, screen-up and depth axes (positive world Z projects upward).
    The maximum projected BBox span includes all three axes and original XYZ
    extents, so elevated geometry and every BBox corner fit conservatively.
    140 mm is a framing policy, not a measurement of a user's physical screen.
    """
    try:
        points = [_numbers(point, 3) for point in boundary_xyz]
    except (TypeError, OverflowError) as error:
        raise ValueError('Expected finite XYZ boundary points') from error
    if not points:
        raise ValueError('Camera requires boundary points')
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    extents = [high[i] - low[i] for i in range(3)]
    if not all(math.isfinite(v) for v in extents) or max(extents) <= 0:
        raise ValueError('Camera boundary must have finite nonzero extent')
    s, t, u = 1 / math.sqrt(2), 1 / math.sqrt(6), 1 / math.sqrt(3)
    matrix = [s, s, 0.0, -t, t, 2 * t, u, -u, u]
    projected_spans = [sum(abs(matrix[axis * 3 + i]) * extents[i] for i in range(3))
                       for axis in range(3)]
    span = max(extents + projected_spans)
    scale = VIRTUAL_VIEW_MM / span
    if not math.isfinite(span) or not math.isfinite(scale) or scale <= 0:
        raise ValueError('Camera framing exceeds finite numeric range')
    return {'origin_mm': [low[i] + extents[i] / 2 for i in range(3)],
            'scale': scale, 'matrix': matrix}


def _validated_spec(spec):
    try:
        origin = _numbers(spec['origin_mm'], 3)
        matrix = _numbers(spec['matrix'], 9)
        scale = spec['scale']
    except (KeyError, TypeError) as error:
        raise ValueError('Incomplete camera specification') from error
    if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
        raise ValueError('Camera scale must be finite and positive')
    rows = [matrix[i:i + 3] for i in (0, 3, 6)]
    if any(abs(sum(a * b for a, b in zip(rows[i], rows[j])) - (i == j)) > 1e-10
           for i in range(3) for j in range(3)):
        raise ValueError('Camera matrix must be orthonormal')
    a, b, c = rows
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                   - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if abs(determinant - 1.0) > 1e-10:
        raise ValueError('Camera matrix must be right handed')
    return origin, matrix, float(scale)


def _require_displayed(part):
    import NXOpen
    displayed = NXOpen.Session.GetSession().Parts.Display
    if displayed is None or displayed.Tag != part.Tag:
        raise ValueError('Presentation requires this Part to be the displayed Part')


def apply_presentation(part, spec):
    """Set semantic layer states and explicit camera on the displayed Part only.

    NX2406 View.SetOrigin takes an ABSOLUTE point. Do not replace it with
    SetRotationTranslationScale's view-space translation or compare raw Origin
    with spec.origin_mm. No Fit call or part save is performed here.
    """
    origin, numbers, scale = _validated_spec(spec)
    _require_displayed(part)
    import NXOpen
    import NXOpen.Layer
    for layer in DISPLAY_LAYERS:
        part.Layers.SetState(layer, NXOpen.Layer.State.Selectable)
    matrix = NXOpen.Matrix3x3()
    for key, value in zip(MATRIX_KEYS, numbers):
        setattr(matrix, key, value)
    view = part.ModelingViews.WorkView
    view.Orient(matrix)
    view.SetOrigin(NXOpen.Point3d(*origin))
    view.SetScale(scale)
    view.RenderingStyle = NXOpen.View.RenderingStyleType.ShadedWithEdges
    return read_presentation(part)


def read_presentation(part):
    """Record native camera and explicit enum comparisons without integer guesses.

    View.Origin is expressed in view coordinates; AbsoluteOrigin is separately
    recorded in model coordinates. Compare recorded native values with reopened
    native values, rather than treating Origin as the requested absolute center.
    AskVisibleObjects and screenshots remain separate rendering evidence.
    """
    _require_displayed(part)
    import NXOpen
    import NXOpen.Layer
    view = part.ModelingViews.WorkView
    origin, absolute, matrix = view.Origin, view.AbsoluteOrigin, view.Matrix
    layers = {}
    for number in DISPLAY_LAYERS:
        state = part.Layers.GetState(number)
        layers[str(number)] = {
            'state': str(state),
            'visible': state in (NXOpen.Layer.State.WorkLayer, NXOpen.Layer.State.Selectable,
                                 NXOpen.Layer.State.Visible),
            'selectable': state in (NXOpen.Layer.State.WorkLayer, NXOpen.Layer.State.Selectable),
            'hidden': state == NXOpen.Layer.State.Hidden}
    return {'camera': {'origin_view_mm': [origin.X, origin.Y, origin.Z],
                       'absolute_origin_mm': [absolute.X, absolute.Y, absolute.Z],
                       'matrix': [getattr(matrix, key) for key in MATRIX_KEYS],
                       'scale': view.Scale},
            'layers': layers, 'rendering_style': str(view.RenderingStyle),
            'shaded_with_edges': view.RenderingStyle == NXOpen.View.RenderingStyleType.ShadedWithEdges}
