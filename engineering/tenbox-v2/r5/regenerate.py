"""Two clean builds, the second from the delivered source ZIP only."""
from pathlib import Path
import argparse, json, subprocess, sys, tempfile, zipfile
import build
ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='tenbox-r5-') as temporary:
        work = args.out.resolve() if args.out else Path(temporary)
        work.mkdir(parents=True, exist_ok=True)
        first, second = work/'clean', work/'extracted-build'
        subprocess.run([sys.executable, str(ROOT/'build.py'), '--out', str(first)], check=True)
        archive = first/'packages/tenbox-v2-r5-source.zip'
        build.verify_zip(archive)
        source = work/'extracted-source'
        with zipfile.ZipFile(archive) as stream:
            stream.extractall(source)
        subprocess.run([sys.executable, str(source/'build.py'), '--out', str(second)], check=True, cwd=source)
        # Export STEP includes legitimate timestamps/UUIDs; check geometry in verify.py.
        for relative in ['10box-v2-r5/model_data.json', 'h2d-r5/meshes/body-bottom-common-print.stl', 'deliverables/10box-v2-r5-preview.html']:
            assert (first/relative).read_bytes() == (second/relative).read_bytes(), relative
        for name in ['tenbox-v2-r5-print.zip', 'tenbox-v2-r5-review.zip', 'tenbox-v2-r5-source.zip']:
            build.verify_zip(second/'packages'/name)
        print(json.dumps({'clean_build': True, 'extracted_source_build': True, 'model_print_stl_viewer_repeatable': True, 'private_checkout_required': False, 'physical_tests_performed': False}))

if __name__ == '__main__':
    main()
