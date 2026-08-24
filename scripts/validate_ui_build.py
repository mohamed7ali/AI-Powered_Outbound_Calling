from outbound_ai.ui.app import build_ui

app = build_ui()
print("ui_build_ok", type(app).__name__)
print("dependency_count", len(getattr(app, "dependencies", [])))
print("login_outputs_and_events_registered")
