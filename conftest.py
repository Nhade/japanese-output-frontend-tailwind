import sys
import os

# Add apps/backend to sys.path so that bare imports (ai_core, graphs, etc.)
# work the same way when running tests as when running the app directly.
backend_path = os.path.join(os.path.dirname(__file__), 'apps', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
