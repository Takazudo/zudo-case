"""Incrementally rebuild accepted R5 in disposable output; publish only explicitly."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, zipfile
ROOT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_zip(target, files):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+target.name, dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        inventory = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
        payload = dict(files)
        payload['MANIFEST.sha256'] = ''.join(f'{sha}  {name}\n' for name, sha in inventory.items()).encode()
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payload.items()):
                entry = zipfile.ZipInfo(name, (2026, 11, 9, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, data)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        verify_zip(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        inventory = archive.read('MANIFEST.sha256').decode().splitlines()
        assert len(inventory) == len(names)-1
        listed = []
        for line in inventory:
            sha, name = line.split('  ', 1)
            assert name not in listed, 'Duplicate manifest path: '+name
            listed.append(name)
            assert hashlib.sha256(archive.read(name)).hexdigest() == sha, name
        assert set(listed) == set(names)-{'MANIFEST.sha256'}, 'Manifest inventory differs from archive'
        return names

def atomic_copy(source, target, kind):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+target.name, dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        assert digest(temporary) == digest(source)
        if kind == 'package':
            verify_zip(temporary)
        elif kind == '3mf':
            with zipfile.ZipFile(temporary) as archive:
                assert archive.testzip() is None
                assert '3D/3dmodel.model' in archive.namelist()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

def files_under(directory, prefix=''):
    return {prefix+p.relative_to(directory).as_posix(): p.read_bytes() for p in sorted(directory.rglob('*'))
            if p.is_file() and not any(x in p.parts for x in ['__pycache__', 'node_modules', '.venv', 'qa'])}

def run(root, relative, *args):
    subprocess.run([sys.executable, str(root/relative), *args], check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--publish-root', type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit('Choose an absent output directory; accepted inputs are never overwritten.')
    shutil.copytree(ROOT/'source', out)
    for relative in ['10box-v2-r5/step', '10box-v2-r5/stl-review', 'h2d-r5/projects']:
        shutil.rmtree(out/relative)
    (out/'h2d-r5/projects').mkdir()
    run(out, '10box-v2-r5/build_geometry.py')
    run(out, '10box-v2-r5/review-checks/verify_floor_exports.py')
    run(out, 'h2d-r5/build_flat_projects.py')
    run(out, 'h2d-r5/verify_flat_packages.py')
    run(out, 'preview-r5/build_preview.py')
    subprocess.run([sys.executable, str(ROOT/'verify.py'), '--out', str(out)], check=True)
    packages = out/'packages'
    print_files = files_under(out/'h2d-r5/projects', 'projects/')
    print_files.update(files_under(out/'h2d-r5/meshes', 'print-oriented-stl/'))
    for name in ['assembly-bom.csv', 'floor-print-pose.json', 'roof-print-pose.json']:
        print_files[name] = (out/'h2d-r5'/name).read_bytes()
    print_files['README.md'] = (ROOT/'README.md').read_bytes()
    assert len([n for n in print_files if n.endswith('.3mf')]) == 15
    assert 'print-oriented-stl/body-bottom-common-print.stl' in print_files
    atomic_zip(packages/'tenbox-v2-r5-print.zip', print_files)
    review = files_under(out/'10box-v2-r5/step', 'assembly-step/')
    review.update(files_under(out/'10box-v2-r5/stl-review', 'assembly-stl/'))
    review['tenbox-v2-r5.html'] = (out/'deliverables/10box-v2-r5-preview.html').read_bytes()
    review['README.md'] = (ROOT/'README.md').read_bytes()
    atomic_zip(packages/'tenbox-v2-r5-review.zip', review)
    source_files = files_under(ROOT/'source', 'source/')
    for name in ['build.py', 'verify.py', 'test_contract.py', 'regenerate.py', 'pyproject.toml', 'uv.lock', '.python-version', 'README.md']:
        source_files[name] = (ROOT/name).read_bytes()
    atomic_zip(packages/'tenbox-v2-r5-source.zip', source_files)
    if args.publish_root:
        repository = args.publish_root.resolve()
        for package in packages.glob('*.zip'):
            target = repository/'public/downloads/candidate'/package.name
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(package, target, 'package')
        target = repository/'public/downloads/candidate/tenbox-v2-r5'
        target.mkdir(exist_ok=True)
        for project in (out/'h2d-r5/projects').glob('*.3mf'):
            atomic_copy(project, target/project.name, '3mf')
        atomic_copy(out/'deliverables/10box-v2-r5-preview.html', repository/'public/previews/tenbox-v2-r5.html', 'html')
    print(json.dumps({'out': str(out), 'packages': {p.name: digest(p) for p in packages.glob('*.zip')}, 'production_approved': False}))

if __name__ == '__main__':
    main()
