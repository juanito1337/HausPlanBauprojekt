# -*- coding: utf-8 -*-
"""Read-only diagnostic journal for the R10 DGM point-distance failure.

No import, no geometry creation, no modification, no part save, no update.
Run in NX with the already imported 01_GELAENDE_R09.prt as Work AND Display Part.
Tests four original reference points; writes a NEW JSON report beside the journal
(or to the user's temporary directory if the journal directory is not writable).
This journal is NOT a geometry release or an automatic fix.
"""
import datetime
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

PATCH = "DGM-PUNKT85-DIAGNOSE-01"
EXPECTED_PART_NAME = "01_GELAENDE_R09.prt"
SOURCE_STEP_SHA256 = "25a972e13beecdd9ebcf2a3420124803c78805263c806162a9785b84e167fd61"
POINT_TOLERANCE_MM = 0.25
# Original R10 samples. R11a carries the IDENTICAL DGM specification.
# Values are coordinates, not results. No source value substitutes an NX result.
POINTS = [
    (84, [36794.9870416, -56307.9919916, 31140.0]),
    (85, [35814.906056, -56109.3937495, 31130.0]),
    (86, [34834.8250705, -55910.7955073, 31120.0]),
    (168, [36013.5042982, -55129.3127639, 31120.0]),
]


def checked_xyz(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError("XYZ-Tupel mit drei Zahlen erwartet")
    out = []
    for number in value:
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ValueError("XYZ-Wert nicht numerisch")
        number = float(number)
        if not math.isfinite(number):
            raise ValueError("XYZ-Wert nicht endlich")
        out.append(number)
    return out


def result_record(result, point):
    """Retain actual returned coordinates, not just the scalar distance."""
    if not isinstance(result, (tuple, list)) or len(result) != 3:
        raise ValueError("AskMinimumDist: drei Ergebnisfelder erwartet")
    d = result[0]
    if isinstance(d, bool) or not isinstance(d, (int, float)):
        raise ValueError("Abstand ist keine Zahl")
    d = float(d)
    if not math.isfinite(d) or d < 0:
        raise ValueError("Abstand negativ oder nicht endlich")
    p1, p2 = checked_xyz(result[1]), checked_xyz(result[2])
    input_error = math.dist(point, p1)
    reconstructed = math.dist(p1, p2)
    consistent = (input_error <= 0.002 and
                  abs(reconstructed - d) <= max(0.002, 1e-7 * d))
    return {
        "distance_mm": d,
        "returned_point_on_input_mm": p1,
        "returned_point_on_target_mm": p2,
        "target_minus_reference_mm": [p2[i] - point[i] for i in range(3)],
        "input_point_error_mm": input_error,
        "distance_recomputed_from_returned_points_mm": reconstructed,
        "result_consistent": consistent,
        "within_unchanged_point_tolerance": consistent and d <= POINT_TOLERANCE_MM,
    }


def run_measurements(modeling, body_tag, face_tags, report, checkpoint, log):
    """Compare old body call with calls to the actual faces, with/without seed.

    A seed is only passed to a FACE, not assumed to work on a body. All distances
    and coordinates come from NX. An exception is retained as a diagnostic result;
    no exception is converted to a successful geometry check.
    """
    if not face_tags or len(face_tags) > 8:
        raise ValueError("Diagnose ist auf ein DGM mit 1 bis 8 Faces begrenzt")
    methods = [("BODY_OHNE_STARTPUNKT_WIE_R10", body_tag, 0)]
    for i, tag in enumerate(face_tags, 1):
        methods.append(("FACE_%d_OHNE_STARTPUNKT" % i, tag, 0))
        methods.append(("FACE_%d_MIT_STARTPUNKT" % i, tag, 1))
    report["points"] = []
    report["planned_calls"] = len(POINTS) * len(methods)
    report["completed_calls"] = 0
    for number, coordinates in POINTS:
        point = checked_xyz(coordinates)
        row = {"source_point_one_based": number, "reference_mm": point, "measurements": []}
        report["points"].append(row)
        for method, tag, seed_flag in methods:
            report["current_operation"] = "%s / Quellpunkt %s" % (method, number)
            measurement = {"method": method, "target_tag": int(tag),
                           "guess2_given": seed_flag,
                           "guess2_mm": list(point) if seed_flag else [0.0, 0.0, 0.0],
                           "status": "AUFRUF_LAEUFT"}
            row["measurements"].append(measurement)
            checkpoint(report)
            log(report["current_operation"])
            start = time.perf_counter()
            try:
                result = modeling.AskMinimumDist(
                    0, tag, 1, list(point), seed_flag, list(measurement["guess2_mm"]))
                measurement.update(result_record(result, point))
                measurement["status"] = "MESSUNG_ERFASST"
            except Exception as error:
                measurement.update(status="MESSUNG_FEHLGESCHLAGEN",
                                   error=str(error), exception_type=type(error).__name__)
                try:
                    measurement["nx_error_code"] = int(error.ErrorCode)
                except (AttributeError, ValueError, TypeError):
                    pass
            finally:
                measurement["duration_seconds"] = time.perf_counter() - start
                report["completed_calls"] += 1
                checkpoint(report)
        valid = [m for m in row["measurements"]
                 if m.get("result_consistent") is True]
        row["valid_numeric_results"] = len(valid)
        row["method_distance_spread_mm"] = (
            max(m["distance_mm"] for m in valid) - min(m["distance_mm"] for m in valid)
            if valid else None)
        # This is ONLY a disagreement marker, never a success/freigabe decision.
        row["methods_disagree_at_point_tolerance"] = (
            row["method_distance_spread_mm"] is not None and
            row["method_distance_spread_mm"] > POINT_TOLERANCE_MM)
        checkpoint(report)
    errors = sum(m["status"] != "MESSUNG_ERFASST" or not m.get("result_consistent", False)
                 for row in report["points"] for m in row["measurements"])
    report["measurement_error_count"] = errors
    report["status"] = "DIAGNOSE_BEENDET_MIT_MESSFEHLERN" if errors else "DIAGNOSE_BEENDET"
    report["geometry_release"] = False
    report["current_operation"] = "KEIN_GEOMETRIEURTEIL; Bericht auswerten"
    checkpoint(report)


def new_report_path():
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = "DGM_PUNKTDIAGNOSE_%s_%s.json" % (stamp, uuid.uuid4().hex[:8])
    dirs = [Path(os.path.abspath(__file__)).parent, Path(tempfile.gettempdir())]
    failures = []
    for directory in dirs:
        path = directory / name
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write("{}\n")
            return path
        except OSError as error:
            failures.append(str(error))
    raise OSError("Kein Diagnosebericht schreibbar: " + "; ".join(failures))


def write_report(path, data):
    temporary = Path(str(path) + ".tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
    os.replace(str(temporary), str(path))


def main():
    path = new_report_path()
    report = {
        "patch": PATCH, "status": "VORPRUEFUNG", "report_file": str(path),
        "started": datetime.datetime.now().isoformat(),
        "expected_source_step_sha256": SOURCE_STEP_SHA256,
        "loaded_NX_geometry_source_hash_verified": False,
        "tolerance_mm": POINT_TOLERANCE_MM,
        "read_only_part_access": True, "part_saved_by_journal": False,
        "geometry_release": False,
        "scope": "Vier Originalpunkte. Keine Importwiederholung, kein Modellaufbau, "
                 "kein Inhalts-/Gesamtformnachweis. Fehlende aktuelle NX-Geometrie nicht ersetzt.",
    }
    write_report(path, report)
    session = None
    try:
        import NXOpen
        import NXOpen.UF
        session = NXOpen.Session.GetSession()
        part, display = session.Parts.Work, session.Parts.Display
        if part is None or display is None:
            raise RuntimeError("Zuerst das bereits importierte 01_GELAENDE_R09.prt separat anzeigen.")
        report["work_part"] = str(part.FullPath)
        report["display_part"] = str(display.FullPath)
        if part.Tag != display.Tag:
            raise RuntimeError("Gelaendeteil muss Work Part UND Display Part sein; nicht im Baugruppenkontext pruefen.")
        if Path(str(part.FullPath)).name.lower() != EXPECTED_PART_NAME.lower():
            raise RuntimeError("Nur das bereits importierte %s separat als Arbeitsteil anzeigen. "
                               "Dieses Journal importiert selbst nichts." % EXPECTED_PART_NAME)
        report["part_units"] = str(part.PartUnits)
        if part.PartUnits != NXOpen.BasePart.Units.Millimeters:
            raise RuntimeError("DGM-Arbeitsteil muss in Millimetern vorliegen; keine Umrechnung ausgefuehrt.")
        bodies = list(part.Bodies)
        if len(bodies) != 1 or bodies[0].IsSolidBody:
            raise RuntimeError("Genau ein offener DGM-Flaechenkoerper erwartet; keine automatische Auswahl.")
        body = bodies[0]
        if body.OwningPart.Tag != part.Tag:
            raise RuntimeError("Koerper gehoert nicht zum DGM-Arbeitsteil.")
        faces = list(body.GetFaces())
        uf = NXOpen.UF.UFSession.GetUFSession()
        report["body_tag"] = int(body.Tag)
        report["face_tags"] = [int(f.Tag) for f in faces]
        report["face_count"] = len(faces)
        # Same six-number bounding-box API as in the house project. Diagnostic only.
        report["nx_body_box_mm"] = list(map(float, uf.ModlGeneral.AskBoundingBox(body.Tag)))
        session.ListingWindow.Open()
        def log(text):
            session.ListingWindow.WriteLine(text)
        report["status"] = "MESSUNGEN_LAUFEN"
        run_measurements(uf.Modeling, body.Tag, [f.Tag for f in faces], report,
                         lambda data: write_report(path, data), log)
        log("Diagnosebericht: " + str(path))
        log("Keine Parts veraendert oder gespeichert. Keine Geometriefreigabe.")
    except Exception as error:
        report.update(status="DIAGNOSE_ABGEBROCHEN", error=str(error),
                      exception_type=type(error).__name__)
        import traceback
        report["traceback"] = traceback.format_exc()
        write_report(path, report)
        message = str(error) + "\nBericht: " + str(path)
        if session is not None:
            try:
                session.ListingWindow.Open()
                session.ListingWindow.WriteLine(message)
            except Exception:
                print(message)
        else:
            print(message)
    finally:
        report["finished"] = datetime.datetime.now().isoformat()
        write_report(path, report)
    return report


if __name__ == "__main__":
    main()
