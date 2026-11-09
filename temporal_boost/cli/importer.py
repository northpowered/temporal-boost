import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _target_is_missing(error: ModuleNotFoundError, module_name: str) -> bool:
    if error.name is None or not (module_name == error.name or module_name.startswith(f"{error.name}.")):
        return False
    # Even a matching name can be raised by application/package initialization code.
    frame = error.__traceback__
    while frame is not None:
        executing_module = frame.tb_frame.f_globals.get("__name__")
        if executing_module == module_name or module_name.startswith(f"{executing_module}."):
            return False
        frame = frame.tb_next
    return True


def _import_app_module(module_name: str) -> ModuleType:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if not _target_is_missing(exc, module_name):
            raise
        missing = exc

    original_path = sys.path.copy()
    working_dir = Path.cwd()
    for candidate in (working_dir, working_dir.parent):
        candidate_str = str(candidate.resolve())
        if candidate_str in sys.path or (candidate == working_dir and "" in sys.path):
            continue
        sys.path.insert(0, candidate_str)
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if not _target_is_missing(exc, module_name):
                raise
            missing = exc
        sys.path[:] = original_path
    raise ValueError(f'Could not import module "{module_name}".') from missing


def import_app_object(app_path: str) -> Any:
    """Resolve module:attribute.nested, retaining only a successful fallback search directory.

    Search the normal Python path, then the working directory and its parent.
    Failed calls restore sys.path; dependency and application errors propagate unchanged.

    Raises:
        ValueError: If the import string is malformed, the target module is missing,
            or an attribute cannot be resolved. Lookup errors are chained as causes.
    """
    try:
        module_str, attribute_path = app_path.split(":", 1)
    except ValueError as exc:
        raise ValueError(f'Import string "{app_path}" must be in format "<module>:<attribute>".') from exc

    if not all(part.isidentifier() for part in (*module_str.split("."), *attribute_path.split("."))):
        raise ValueError(f'Import string "{app_path}" must be in format "<module>:<attribute>".')

    original_path = sys.path.copy()
    try:
        instance: Any = _import_app_module(module_str)
        try:
            for attribute in attribute_path.split("."):
                instance = getattr(instance, attribute)
        except AttributeError as exc:
            raise ValueError(f'Attribute "{attribute_path}" not found in module "{module_str}".') from exc
        return instance
    except BaseException:
        sys.path[:] = original_path
        raise
