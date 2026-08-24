import json
from outbound_ai.ui.app import build_ui

app = build_ui()
config = app.get_config_file()
print('config_keys=', sorted(config.keys()))
print('component_count=', len(config.get('components', [])))
for component in config.get('components', []):
    props = component.get('props', {})
    label = props.get('label')
    value = props.get('value')
    visible = props.get('visible')
    if component.get('type') in {'tabs', 'tabitem', 'tab', 'column'} or label in {'المؤسسة الحالية', 'الدور'}:
        print('component', component.get('id'), component.get('type'), 'label=', repr(label), 'visible=', repr(visible), 'value=', repr(value), 'parent=', component.get('parent'))
print('dependency_count=', len(config.get('dependencies', [])))
for dep in config.get('dependencies', []):
    fn_index = dep.get('id', dep.get('fn_index'))
    outputs = dep.get('outputs', dep.get('targets'))
    if outputs:
        print('dependency', fn_index, 'outputs=', outputs)
