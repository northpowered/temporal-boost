import importlib
import sys
from pathlib import Path
from typing import Any


def import_app_object(app_path: str) -> Any:
    try:
        module_str, attribute_path = app_path.split(":", 1)
    except ValueError as exc:
        raise ValueError(f'Import string "{app_path}" must be in format "<module>:<attribute>".') from exc

    if not module_str or not attribute_path:
        raise ValueError(f'Import string "{app_path}" must be in format "<module>:<attribute>".')

    try:
        module = importlib.import_module(module_str)
    except ModuleNotFoundError as exc:
        candidates: list[Path] = []
        current_working_dir = Path.cwd()
        first_segment = module_str.split(".")[0]
        if (current_working_dir / first_segment).exists():
            candidates.append(current_working_dir)
        candidates.append(current_working_dir.parent)
        for candidate in candidates:
            candidate_str = str(candidate.resolve())
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            try:
                module = importlib.import_module(module_str)
                break
            except ModuleNotFoundError:
                continue
        else:
            raise ValueError(f'Could not import module "{module_str}".') from exc

    instance: Any = module
    for attribute in attribute_path.split("."):
        if not hasattr(instance, attribute):
            raise ValueError(f'Attribute "{attribute_path}" not found in module "{module_str}".')
        instance = getattr(instance, attribute)
    return instance
