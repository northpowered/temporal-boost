import importlib
import sys
import traceback
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from temporal_boost.cli.importer import import_app_object
from temporal_boost.cli.runner import cli_app


@pytest.fixture
def module_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, str]]:
    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    prefix = f"tb019_{uuid.uuid4().hex}"
    try:
        yield working, prefix
    finally:
        for name in list(sys.modules):
            if name.startswith(prefix):
                del sys.modules[name]
        importlib.invalidate_caches()


def write_module(root: Path, name: str, source: str) -> Path:
    path = root / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    importlib.invalidate_caches()
    return path


@pytest.mark.parametrize(
    "app_path",
    ["", "app", ":app", "app:", "app::app", "app:app.", "app..main:app", "app:app()", " app:app"],
)
def test_malformed_import_string_does_not_attempt_import(app_path: str) -> None:
    original_path = sys.path.copy()
    with patch("temporal_boost.cli.importer.importlib.import_module") as import_module:
        with pytest.raises(ValueError, match="must be in format"):
            import_app_object(app_path)
    import_module.assert_not_called()
    assert sys.path == original_path


@pytest.mark.parametrize("suffix", ["", ".missing", ".missing.module"])
def test_missing_target_preserves_cause_and_restores_path(module_tree: tuple[Path, str], suffix: str) -> None:
    _, prefix = module_tree
    original_path = sys.path.copy()
    target = prefix + suffix
    with pytest.raises(ValueError, match=f'Could not import module "{target}"') as caught:
        import_app_object(f"{target}:app")
    assert isinstance(caught.value.__cause__, ModuleNotFoundError)
    assert caught.value.__cause__.name == prefix
    assert sys.path == original_path


@pytest.mark.parametrize("location", ["path", "current", "parent"])
def test_successful_search_retains_only_the_used_directory_for_deferred_imports(
    module_tree: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    working, prefix = module_tree
    root = working if location == "current" else working.parent
    if location == "path":
        monkeypatch.syspath_prepend(str(root))
    # For the parent case, force an unsuccessful current-directory candidate first.
    if location == "parent":
        (working / prefix).mkdir()
        # A missing submodule in a namespace package allows search in the next root.
        package = root / prefix
        package.mkdir()
        module_name = f"{prefix}.main"
        module = package / "main.py"
    else:
        module_name = prefix
        module = root / f"{prefix}.py"
    dependency = f"{prefix}_late"
    write_module(root, dependency, "value = 42\n")
    module.write_text(f"def app():\n    from {dependency} import value\n    return value\n", encoding="utf-8")
    original_path = sys.path.copy()
    app = import_app_object(f"{module_name}:app")
    assert app() == 42
    expected = original_path if location == "path" else [str(root.resolve()), *original_path]
    assert sys.path == expected


@pytest.mark.parametrize("location", ["path", "current", "parent"])
@pytest.mark.parametrize(
    ("failure", "error_type", "message"),
    [
        ("import {dependency}", ModuleNotFoundError, "{dependency}"),
        ("raise ModuleNotFoundError('manual missing module')", ModuleNotFoundError, "manual missing module"),
        ("raise ImportError('broken dependency API')", ImportError, "broken dependency API"),
        ("raise RuntimeError('application initialization failed')", RuntimeError, "application initialization failed"),
        ("raise SystemExit('application exit')", SystemExit, "application exit"),
        ("raise KeyboardInterrupt('application interrupt')", KeyboardInterrupt, "application interrupt"),
        (
            "raise ModuleNotFoundError('application-named failure', name=__name__)",
            ModuleNotFoundError,
            "application-named failure",
        ),
        ("app = ", SyntaxError, "invalid syntax"),
    ],
)
def test_application_import_failure_is_not_retried_or_reclassified(  # noqa: PLR0913
    module_tree: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    location: str,
    *,
    failure: str,
    error_type: type[BaseException],
    message: str,
) -> None:
    working, prefix = module_tree
    root = working if location == "current" else working.parent
    if location == "path":
        monkeypatch.syspath_prepend(str(root))
    attempts = root / "attempts.txt"
    dependency = f"{prefix}_missing_dependency"
    source = (
        "from pathlib import Path\n"
        f"with Path({str(attempts)!r}).open('a') as attempts:\n    attempts.write('attempt\\n')\n"
        + failure.format(dependency=dependency)
        + "\n"
    )
    module_path = write_module(root, prefix, source)
    original_path = sys.path.copy()
    with pytest.raises(error_type, match=message.format(dependency=dependency)) as caught:
        import_app_object(f"{prefix}:app")
    assert sys.path == original_path
    assert caught.value.__cause__ is None
    if error_type is SyntaxError:
        assert caught.value.filename == str(module_path)
    else:
        assert attempts.read_text(encoding="utf-8") == "attempt\n"
        assert str(module_path) in {frame.filename for frame in traceback.extract_tb(caught.value.__traceback__)}
    if error_type is ModuleNotFoundError and "import " in failure:
        assert caught.value.name == dependency


@pytest.mark.parametrize("failure_in_init", [False, True])
def test_dependency_under_app_package_is_not_a_missing_target(
    module_tree: tuple[Path, str], failure_in_init: bool
) -> None:
    working, prefix = module_tree
    package = working / prefix
    package.mkdir()
    source = f"import {prefix}.dependency\n"
    (package / "__init__.py").write_text(source if failure_in_init else "", encoding="utf-8")
    (package / "main.py").write_text("" if failure_in_init else source, encoding="utf-8")
    original_path = sys.path.copy()
    with pytest.raises(ModuleNotFoundError) as caught:
        import_app_object(f"{prefix}.main:app")
    assert caught.value.name == f"{prefix}.dependency"
    assert sys.path == original_path


def test_nested_attributes_are_resolved_once(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    write_module(
        working,
        prefix,
        """
class Application:
    calls = 0
    @property
    def nested(self):
        self.calls += 1
        return self.calls
app = Application()
""",
    )
    assert import_app_object(f"{prefix}:app.nested") == 1


@pytest.mark.parametrize("attribute", ["missing", "app.missing"])
def test_missing_attribute_has_its_own_diagnostic_and_does_not_retain_fallback(
    module_tree: tuple[Path, str], attribute: str
) -> None:
    working, prefix = module_tree
    write_module(working, prefix, "app = object()\n")
    original_path = sys.path.copy()
    with pytest.raises(ValueError, match=r"Attribute.*not found") as caught:
        import_app_object(f"{prefix}:{attribute}")
    assert isinstance(caught.value.__cause__, AttributeError)
    assert sys.path == original_path


def test_nested_package_and_attribute_import(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    package = working / prefix
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    write_module(package, "main", "from types import SimpleNamespace\napp = SimpleNamespace(nested=42)\n")
    assert import_app_object(f"{prefix}.main:app.nested") == 42


def test_missing_submodule_in_existing_package_preserves_target_cause(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    package = working / prefix
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    original_path = sys.path.copy()
    with pytest.raises(ValueError, match="Could not import module") as caught:
        import_app_object(f"{prefix}.missing:app")
    assert isinstance(caught.value.__cause__, ModuleNotFoundError)
    assert caught.value.__cause__.name == f"{prefix}.missing"
    assert sys.path == original_path


def test_search_does_not_walk_above_parent(module_tree: tuple[Path, str], monkeypatch: pytest.MonkeyPatch) -> None:
    working, prefix = module_tree
    nested = working / "child" / "grandchild"
    nested.mkdir(parents=True)
    write_module(working, prefix, "app = 42\n")
    monkeypatch.chdir(nested)
    original_path = sys.path.copy()
    with pytest.raises(ValueError, match="Could not import module"):
        import_app_object(f"{prefix}:app")
    assert sys.path == original_path


def test_existing_working_directory_entry_is_not_added_again(
    module_tree: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    working, prefix = module_tree
    monkeypatch.setattr(sys, "path", ["", str(working.parent.resolve()), *sys.path])
    original_path = sys.path.copy()
    with pytest.raises(ValueError, match="Could not import module"):
        import_app_object(f"{prefix}:app")
    assert sys.path == original_path


def test_repeated_success_does_not_accumulate_search_directories(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    write_module(working.parent, prefix, "app = object()\n")
    original_path = sys.path.copy()
    first = import_app_object(f"{prefix}:app")
    assert import_app_object(f"{prefix}:app") is first
    assert sys.path == [str(working.parent.resolve()), *original_path]


def test_attribute_runtime_error_is_preserved_and_restores_path(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    write_module(
        working,
        prefix,
        """
failure = RuntimeError("property initialization failed")
class Application:
    @property
    def nested(self):
        raise failure
app = Application()
""",
    )
    original_path = sys.path.copy()
    with pytest.raises(RuntimeError, match="property initialization failed") as caught:
        import_app_object(f"{prefix}:app.nested")
    assert caught.value is sys.modules[prefix].failure
    assert sys.path == original_path


def test_failed_application_path_mutations_are_restored(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    write_module(
        working, prefix, "import sys\nsys.path.append('unexpected-path')\nraise RuntimeError('startup failed')\n"
    )
    original_path = sys.path.copy()
    with pytest.raises(RuntimeError, match="startup failed"):
        import_app_object(f"{prefix}:app")
    assert sys.path == original_path


def test_external_cli_preserves_dependency_failure(module_tree: tuple[Path, str]) -> None:
    working, prefix = module_tree
    dependency = f"{prefix}_dependency"
    write_module(working, prefix, f"import {dependency}\n")
    original_path = sys.path.copy()
    result = CliRunner().invoke(cli_app, [f"{prefix}:app", "--", "run", "all"])
    assert result.exit_code == 1
    assert isinstance(result.exception, ModuleNotFoundError)
    assert result.exception.name == dependency
    assert sys.path == original_path
