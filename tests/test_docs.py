"""The documentation must match the code. These tests read both and compare them."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DOCS = sorted((ROOT / "docs").glob("*.md"))
ALL_DOCS = [README, *DOCS]
HTTP_METHODS = {"get", "post", "patch", "delete", "put"}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def all_text() -> str:
    return "\n".join(text(path) for path in ALL_DOCS)


def endpoints() -> set[str]:
    """Every 'METHOD /path' served by app/api/routes, read from the source."""
    found = set()
    for path in (ROOT / "app" / "api" / "routes").glob("*.py"):
        tree = ast.parse(text(path))
        prefix = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "APIRouter":
                for keyword in node.keywords:
                    if keyword.arg == "prefix":
                        prefix = ast.literal_eval(keyword.value)
        for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for decorator in function.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in HTTP_METHODS):
                    sub = ast.literal_eval(decorator.args[0]) if decorator.args else ""
                    found.add(f"{decorator.func.attr.upper()} {prefix}{sub}")
    return found


def test_every_relative_link_and_image_exists():
    missing = []
    for doc in ALL_DOCS:
        for target in re.findall(r"\]\(([^)\s]+)\)", text(doc)):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if not (doc.parent / target.split("#")[0]).exists():
                missing.append(f"{doc.name} -> {target}")
    assert not missing, missing


def test_the_readme_links_to_every_document():
    readme = text(README)
    unlinked = [doc.name for doc in DOCS if f"docs/{doc.name}" not in readme]
    assert not unlinked, unlinked


def test_every_setting_is_documented_in_the_readme():
    tree = ast.parse(text(ROOT / "app" / "core" / "config.py"))
    settings_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings")
    names = [n.target.id.upper() for n in settings_class.body if isinstance(n, ast.AnnAssign)]
    assert names, "no settings found"
    readme = text(README)
    undocumented = [name for name in names if f"`{name}`" not in readme]
    assert not undocumented, undocumented


def test_every_endpoint_is_documented_in_the_usage_guide():
    usage = text(ROOT / "docs" / "usage.md")
    found = endpoints()
    assert len(found) >= 15, found
    undocumented = sorted(e for e in found if e not in usage)
    assert not undocumented, undocumented


def test_every_rule_type_is_documented_in_the_usage_guide():
    usage = text(ROOT / "docs" / "usage.md")
    rule_types = re.findall(
        r'rule_type = "(\w+)"', "".join(text(p) for p in (ROOT / "app" / "quality" / "rules").glob("*.py"))
    )
    assert len(rule_types) == 6, rule_types
    undocumented = [r for r in rule_types if f"`{r}`" not in usage]
    assert not undocumented, undocumented


def test_every_table_is_documented_in_the_database_design():
    design = text(ROOT / "docs" / "database_design.md")
    tables = re.findall(
        r'__tablename__ = "(\w+)"', "".join(text(p) for p in (ROOT / "app" / "models").glob("*.py"))
    )
    assert len(tables) >= 8, tables
    undocumented = [t for t in tables if f"`{t}`" not in design]
    assert not undocumented, undocumented


def test_every_migration_is_documented():
    migrations = text(ROOT / "docs" / "migrations.md")
    revisions = [p.stem for p in (ROOT / "migrations" / "versions").glob("0*.py")]
    assert len(revisions) >= 3, revisions
    undocumented = [r for r in revisions if f"`{r}`" not in migrations]
    assert not undocumented, undocumented


def test_every_script_the_docs_mention_exists():
    scripts = {p.stem for p in (ROOT / "scripts").iterdir() if p.is_file()}
    mentioned = set(re.findall(r"scripts[\\/.](\w+)", all_text()))
    missing = sorted(name for name in mentioned if name not in scripts)
    assert not missing, missing


def test_every_python_module_the_docs_run_exists():
    modules = set(re.findall(r"python -m ((?:app|scripts)\.\w+)", all_text()))
    assert "app.cli" in modules
    missing = [m for m in modules if not (ROOT / (m.replace(".", "/") + ".py")).exists()]
    assert not missing, missing


def test_every_sample_file_the_docs_mention_exists():
    mentioned = set(re.findall(r"sample_data/[\w./-]+\.\w+", all_text()))
    assert mentioned, "the docs should mention the sample files"
    missing = sorted(m for m in mentioned if not (ROOT / m).exists())
    assert not missing, missing
