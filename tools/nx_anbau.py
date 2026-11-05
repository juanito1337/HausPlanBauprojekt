"""Build or check the independently verified flat M02 main assembly."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def argument_parser():
    from renovierung.anbau.runner import DEFAULT_BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'repair', 'repair-names', 'repair-defaults', 'check'))
    parser.add_argument('--nx-root', type=Path, default=Path('C:/Siemens/NX2406'))
    parser.add_argument('--base', default=DEFAULT_BASE)
    parser.add_argument('--accept-model-assumptions', action='store_true')
    parser.add_argument('--reuse-assets', type=Path,
                        help='Explicit M02_NATIVE_ASSETS_V1 bundle; complete M02 verification is still required')
    parser.add_argument('--candidate', help='Explicit unpublished cad/nx/m02/<stamp> candidate for repair')
    return parser


def main(argv=None):
    from renovierung.anbau.runner import build_extension, repair_extension, check_extension
    args = argument_parser().parse_args(argv)
    try:
        if args.command == 'build':
            if args.candidate:
                raise ValueError('--candidate applies only to repair')
            path = build_extension(args.nx_root, args.accept_model_assumptions, args.base, args.reuse_assets)
            print('PASS M02: vollstaendig nativ gepruefte Lieferung ' + str(path))
        elif args.command in ('repair', 'repair-names', 'repair-defaults'):
            if not args.candidate or args.reuse_assets:
                raise ValueError('repair needs --candidate and does not accept --reuse-assets')
            path = repair_extension(args.nx_root, args.accept_model_assumptions, args.candidate,
                                    naming=args.command == 'repair-names', defaults=args.command == 'repair-defaults')
            print('PASS M02: reparierte und vollstaendig nativ gepruefte Lieferung ' + str(path))
        else:
            if args.reuse_assets or args.candidate:
                raise ValueError('--reuse-assets/--candidate do not apply to check')
            errors = check_extension()
            if errors:
                raise ValueError('; '.join(errors))
            print('PASS M02: native Nachweise und aktuelle Quellen stimmen ueberein (kein neuer NX-Lauf)')
        return 0
    except Exception as error:
        print('FAIL ANBAU: ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
