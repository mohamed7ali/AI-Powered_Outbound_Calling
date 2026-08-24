from outbound_ai.ui.app import build_ui

app = build_ui()
print('gradio_components')
for component in getattr(app, 'blocks', {}).values():
    component_type = type(component).__name__
    label = getattr(component, 'label', None)
    visible = getattr(component, 'visible', None)
    value = getattr(component, 'value', None)
    if component_type in {'Tabs', 'Tab', 'Column', 'Row', 'Markdown', 'Dropdown', 'Button'} or label:
        print(component._id, component_type, 'label=', repr(label), 'visible=', repr(visible), 'value=', repr(value))
print('dependencies', len(getattr(app, 'dependencies', [])))
for index, dependency in enumerate(getattr(app, 'dependencies', [])):
    targets = dependency.get('outputs', []) if isinstance(dependency, dict) else []
    if targets:
        print('dep', index, 'fn=', dependency.get('fn') if isinstance(dependency, dict) else None, 'outputs=', targets)
