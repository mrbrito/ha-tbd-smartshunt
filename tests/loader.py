"""Offline test loader; avoids importing Home Assistant's package initializer."""
import importlib.util
from pathlib import Path
import sys
import types

BASE = Path(__file__).resolve().parents[1] / 'custom_components' / 'tbd_smartshunt'
PACKAGE = '_tbd_test'
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(BASE)]
    sys.modules[PACKAGE] = package

def load(name):
    full = f'{PACKAGE}.{name}'
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, BASE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module
