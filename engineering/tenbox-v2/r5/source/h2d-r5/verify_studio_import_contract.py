"""Check the pinned Studio XML dispatch contract without claiming Studio load.

The importer uses XML_ParserCreate(nullptr), so namespace prefixes remain in
element names. The Relationship/model/config tag dispatches below deliberately
use raw Expat names, unlike the earlier namespace-aware package verifier.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, math, posixpath, uuid, zipfile
import xml.parsers.expat
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PINNED_COMMIT = '4c2c19a4bf698edf153555dfe28fd4f81d6550be'
SOURCE_URL = 'https://github.com/bambulab/BambuStudio/blob/'+PINNED_COMMIT+'/src/libslic3r/Format/bbs_3mf.cpp'
CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
RELS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
MODEL_NAMES = {'model', 'resources', 'object', 'mesh', 'vertices', 'vertex',
               'triangles', 'triangle', 'components', 'component', 'build', 'item', 'metadata'}
CONFIG_NAMES = {'config', 'object', 'part', 'metadata', 'plate', 'model_instance',
                'assemble', 'assemble_item'}


def raw_events(payload):
    parser = xml.parsers.expat.ParserCreate()  # same namespace mode as Studio
    stack, events = [], []
    def start(name, attributes):
        events.append((name, dict(attributes), tuple(stack)))
        stack.append(name)
    def end(name):
        assert stack.pop() == name
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(payload, True)
    assert not stack
    return events


def root_model_targets(payload):
    targets = []
    for name, attributes, _ in raw_events(payload):
        # Exact bbs_3mf.cpp 5555 and 5578 dispatch/recognition, not local-name matching.
        if name == 'Relationship':
            kind = attributes.get('Type', '')
            if kind.startswith('http://schemas.microsoft.com/3dmanufacturing/') and kind.endswith('3dmodel'):
                targets.append(attributes.get('Target', ''))
    return targets


def transform(value, length=12):
    values = [float(v) for v in value.split()]
    assert len(values) == length and all(math.isfinite(v) for v in values)
    return values


def metadata(node):
    return {n.get('key'): n.get('value') for n in node.findall('metadata')}


def audit(path, template_settings=None):
    result = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'source_dispatch_contract_pass': False, 'studio_application_loaded': False,
              'sliced': False, 'errors': []}
    try:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert len(z.namelist()) == len(set(z.namelist()))
            data = {n: z.read(n) for n in z.namelist()}
        for name in data:
            assert not name.startswith('/') and '..' not in Path(name).parts
        relationships = raw_events(data['_rels/.rels'])
        result['relationship_element_names'] = sorted({e[0] for e in relationships})
        targets = root_model_targets(data['_rels/.rels'])
        result['recognized_main_model_targets'] = targets
        if not targets:
            raise ValueError('Pinned Studio relationship dispatch sees no main model target; importer returns false before model parsing (bbs_3mf.cpp2139–2140).')
        assert targets == ['/3D/3dmodel.model']
        for member, payload in data.items():
            if member.endswith('.rels'):
                events = raw_events(payload)
                assert events[0][0] == 'Relationships' and events[0][1].get('xmlns') == RELS
                assert all(n in {'Relationships', 'Relationship'} for n, _, _ in events)
                rel_ids = []
                for name, attributes, _ in events:
                    if name != 'Relationship':
                        continue
                    rel_ids.append(attributes['Id'])
                    if attributes.get('TargetMode') != 'External':
                        target = attributes['Target']
                        base = str(Path(member).parent.parent)
                        target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(base, target))
                        assert target in data
                assert len(rel_ids) == len(set(rel_ids))
        content = raw_events(data['[Content_Types].xml'])
        assert content[0][0] == 'Types' and content[0][1].get('xmlns') == CT
        assert all(n in {'Types', 'Default', 'Override'} for n, _, _ in content)
        assert any(n == 'Default' and a.get('Extension') == 'model' and
                   a.get('ContentType') == 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml'
                   for n, a, _ in content)
        model_payload = data['3D/3dmodel.model']
        model_events = raw_events(model_payload)
        model_names = sorted({e[0] for e in model_events})
        assert set(model_names) <= MODEL_NAMES, 'Model tag prefix/unsupported element would bypass pinned dispatch'
        first = model_events[0]
        assert first[0] == 'model' and first[1].get('xmlns') == CORE
        assert first[1].get('unit', 'millimeter') == 'millimeter'
        assert first[1].get('xmlns:p') == PROD
        assert first[1].get('requiredextensions') == 'p'
        uuids = []
        for name, attrs, _ in model_events:
            for key, value in attrs.items():
                if key.lower().endswith(':uuid'):
                    assert key in {'p:UUID', 'p:uuid'}, 'UUID prefix is not recognized by pinned importer'
                    uuid.UUID(value)
                    uuids.append(value)
            if 'transform' in attrs:
                transform(attrs['transform'])
        assert len(uuids) == len(set(uuids))
        model = ET.fromstring(model_payload)
        objects = {n.get('id'): n for n in model.findall('{*}resources/{*}object')}
        assert len(objects) == len(model.findall('{*}resources/{*}object'))
        assert objects and all(int(k) > 0 for k in objects)
        mesh_ids, mesh_count = set(), 0
        for oid, obj in objects.items():
            assert obj.get('type', 'model') == 'model'
            mesh = obj.find('{*}mesh')
            components = obj.findall('{*}components/{*}component')
            assert (mesh is not None) != bool(components)
            if mesh is not None:
                mesh_count += 1
                mesh_ids.add(oid)
                vertices = mesh.findall('{*}vertices/{*}vertex')
                triangles = mesh.findall('{*}triangles/{*}triangle')
                assert vertices and triangles
                assert all(math.isfinite(float(v.get(axis))) for v in vertices for axis in ['x', 'y', 'z'])
                assert all(0 <= int(t.get(axis)) < len(vertices) for t in triangles for axis in ['v1', 'v2', 'v3'])
            for c in components:
                assert c.get('objectid') in objects and c.get('objectid') != oid
        items = model.findall('{*}build/{*}item')
        build_ids = [n.get('objectid') for n in items]
        assert items and all(i in objects for i in build_ids)
        configuration = data['Metadata/model_settings.config']
        config_events = raw_events(configuration)
        config_names = sorted({e[0] for e in config_events})
        assert set(config_names) <= CONFIG_NAMES, 'Configuration tag prefix/unsupported element would bypass pinned dispatch'
        assert config_events[0][0] == 'config'
        config = ET.fromstring(configuration)
        conf_objects = {n.get('id'): n for n in config.findall('object')}
        assert len(conf_objects) == len(config.findall('object')) and set(conf_objects) == set(build_ids)
        for oid, node in conf_objects.items():
            component_ids = {c.get('objectid') for c in objects[oid].findall('{*}components/{*}component')}
            for part in node.findall('part'):
                assert part.get('id') in mesh_ids and part.get('id') in component_ids
                assert part.get('subtype') == 'normal_part'
                transform(metadata(part)['matrix'], 16)
            assert node.findall('part')
        plates = config.findall('plate')
        assert len(plates) == 1 and metadata(plates[0])['plater_id'] == '1'
        instance_ids, identification_ids = [], []
        for node in plates[0].findall('model_instance'):
            m = metadata(node)
            assert m['object_id'] in build_ids and int(m['instance_id']) == 0
            instance_ids.append(m['object_id'])
            identification_ids.append(m['identify_id'])
        assert Counter(instance_ids) == Counter(build_ids)
        assert len(identification_ids) == len(set(identification_ids))
        assembled = config.findall('assemble/assemble_item')
        assert Counter(n.get('object_id') for n in assembled) == Counter(build_ids)
        for node in assembled:
            assert node.get('instance_id') == '0'
            transform(node.get('transform'))
            transform(node.get('offset'), 3)
        settings_bytes = data['Metadata/project_settings.config']
        settings = json.loads(settings_bytes)
        if template_settings is not None:
            assert settings_bytes == template_settings
        count = len(settings['filament_settings_id'])
        assert all(len(settings[k]) == count for k in ['filament_map', 'filament_nozzle_map', 'filament_colour', 'filament_type'])
        assert count == 2 and all(1 <= int(metadata(n)['extruder']) <= count for n in conf_objects.values())
        plate = metadata(plates[0])
        mode = plate.get('filament_map_mode', settings['filament_map_mode'])
        assert mode in {'Manual', 'Auto For Flush', 'Auto For Match', 'Default'}
        if 'filament_maps' in plate:
            mapping = [int(v) for v in plate['filament_maps'].split()]
            assert len(mapping) == count and all(v in [1, 2] for v in mapping)
            assert mode == 'Manual' and mapping == [1, 1]
        result.update({'source_dispatch_contract_pass': True, 'model_element_names': model_names,
                       'configuration_element_names': config_names, 'model_resource_count': len(objects),
                       'mesh_count': mesh_count, 'build_instance_count': len(items), 'uuid_prefixes_and_values_valid': True,
                       'object_part_plate_assembly_references_resolve': True,
                       'content_types_checked': True, 'effective_filament_map_mode': mode,
                       'filament_count': count, 'project_settings_sha256': hashlib.sha256(settings_bytes).hexdigest(),
                       'settings_bytes_match_template': settings_bytes == template_settings if template_settings is not None else None})
    except Exception as e:
        result['errors'].append(str(e) or type(e).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects-dir', type=Path)
    parser.add_argument('--include-frozen', action='store_true')
    parser.add_argument('--allow-failure', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'studio-import-contract-review.json')
    args = parser.parse_args()
    if args.projects_dir:
        project_dir = args.projects_dir
    else:
        expected = json.loads((ROOT/'h2d-project-report.json').read_text())
        project_dir = ROOT/expected.get('projects_directory', 'projects')
    with zipfile.ZipFile(ROOT/'source-template/h2d-empty.3mf') as z:
        original_settings = z.read('Metadata/project_settings.config')
    paths = sorted(project_dir.glob('*.3mf'))
    if args.include_frozen:
        paths += sorted((ROOT/'source-flat-r4').glob('*.3mf'))
    records = [audit(p, original_settings) for p in paths]
    result = {'schema': '10box-r5-studio-import-contract/1',
              'scope': 'Namespace-unaware Expat plus exact pinned Studio tag dispatch, OPC/model/config references, UUID prefixes and saved settings. This is a focused import contract check, not a complete Studio application load or slice.',
              'pinned_commit': PINNED_COMMIT, 'source_url': SOURCE_URL,
              'source_lines': {'parser_namespace_mode': 2916, 'relationship_dispatch': 5555,
                               'empty_model_path_rejection': [2139, 2140], 'model_dispatch': [3907, 3946],
                               'configuration_dispatch': [4001, 4040]},
              'archive_count': len(records), 'passed_count': sum(r['source_dispatch_contract_pass'] for r in records),
              'failed_count': sum(not r['source_dispatch_contract_pass'] for r in records),
              'all_source_dispatch_contracts_pass': bool(records) and all(r['source_dispatch_contract_pass'] for r in records),
              'studio_application_loaded': False, 'sliced': False, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['archive_count', 'passed_count', 'failed_count',
                                           'all_source_dispatch_contracts_pass', 'studio_application_loaded', 'sliced']}))
    if not args.allow_failure:
        assert result['all_source_dispatch_contracts_pass'], 'See '+str(args.output)


if __name__ == '__main__':
    main()
