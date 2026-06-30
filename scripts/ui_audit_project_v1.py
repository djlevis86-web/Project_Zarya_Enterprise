from pathlib import Path
from datetime import datetime
import re
import subprocess


BASE_DIR = Path(__file__).resolve().parents[1]

IGNORE_DIRS = {
    ".git",
    "venv",
    ".venv",
    "env",
    "node_modules",
    "__pycache__",
    "media",
    "staticfiles",
    "releases",
    "backups",
    "backups_db",
    "backups_media",
}

REPORT_PATH = BASE_DIR / "docs" / "UI_AUDIT_REPORT_RAW.md"


def should_ignore(path: Path) -> bool:
    parts = set(path.parts)

    return bool(parts & IGNORE_DIRS)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def count_lines(text: str) -> int:
    if not text:
        return 0

    return len(text.splitlines())


def git_output(args):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=BASE_DIR,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as exc:
        return f"git error: {exc}"


def collect_files(pattern: str):
    return sorted(
        path
        for path in BASE_DIR.rglob(pattern)
        if path.is_file() and not should_ignore(path.relative_to(BASE_DIR))
    )


def rel(path: Path) -> str:
    return path.relative_to(BASE_DIR).as_posix()


def main():
    templates = collect_files("*.html")
    css_files = collect_files("*.css")
    js_files = collect_files("*.js")

    app_css = BASE_DIR / "static" / "css" / "app.css"

    report = []

    report.append("# UI Audit Raw Report")
    report.append("")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## Git")
    report.append("")
    report.append("```text")
    report.append(git_output(["status", "--short", "--branch"]))
    report.append("")
    report.append(git_output(["log", "--oneline", "--decorate", "-8"]))
    report.append("```")
    report.append("")

    report.append("## File summary")
    report.append("")
    report.append(f"- HTML templates: {len(templates)}")
    report.append(f"- CSS files: {len(css_files)}")
    report.append(f"- JS files: {len(js_files)}")
    report.append("")

    report.append("## Templates")
    report.append("")
    report.append("| File | Lines | Extends base | style attrs | `<style>` | inline `<script>` |")
    report.append("|---|---:|---:|---:|---:|---:|")

    templates_without_extends = []
    templates_with_inline_styles = []

    for path in templates:
        text = read_text(path)
        has_extends = "{% extends" in text
        style_attrs = len(re.findall(r"\sstyle\s*=", text, flags=re.I))
        style_tags = len(re.findall(r"<style\b", text, flags=re.I))
        script_tags = len(re.findall(r"<script\b", text, flags=re.I))

        if not has_extends and "login.html" not in path.name:
            templates_without_extends.append(path)

        if style_attrs or style_tags:
            templates_with_inline_styles.append((path, style_attrs, style_tags))

        report.append(
            f"| `{rel(path)}` | {count_lines(text)} | "
            f"{'yes' if has_extends else 'no'} | "
            f"{style_attrs} | {style_tags} | {script_tags} |"
        )

    report.append("")
    report.append("## CSS files")
    report.append("")
    report.append("| File | Lines | `!important` | hard colors | media queries | z-index | fixed/sticky |")
    report.append("|---|---:|---:|---:|---:|---:|---:|")

    for path in css_files:
        text = read_text(path)

        important = text.count("!important")
        hard_colors = len(re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\(", text))
        media_queries = len(re.findall(r"@media\b", text))
        z_index = len(re.findall(r"z-index\s*:", text, flags=re.I))
        fixed_sticky = len(re.findall(r"position\s*:\s*(fixed|sticky)", text, flags=re.I))

        report.append(
            f"| `{rel(path)}` | {count_lines(text)} | "
            f"{important} | {hard_colors} | {media_queries} | {z_index} | {fixed_sticky} |"
        )

    report.append("")

    report.append("## app.css import order")
    report.append("")

    if app_css.exists():
        app_text = read_text(app_css)
        imports = re.findall(r'@import\s+url\(["\']?([^"\')]+)["\']?\)', app_text)

        report.append("| # | Import | Exists |")
        report.append("|---:|---|---:|")

        for index, import_path in enumerate(imports, start=1):
            target = (app_css.parent / import_path).resolve()
            report.append(
                f"| {index} | `{import_path}` | {'yes' if target.exists() else 'NO'} |"
            )
    else:
        report.append("`static/css/app.css` not found.")

    report.append("")

    report.append("## JS files")
    report.append("")
    report.append("| File | Lines |")
    report.append("|---|---:|")

    for path in js_files:
        text = read_text(path)
        report.append(f"| `{rel(path)}` | {count_lines(text)} |")

    report.append("")

    report.append("## Potential UI risks")
    report.append("")

    report.append("### Templates without `{% extends %}`")
    report.append("")

    if templates_without_extends:
        for path in templates_without_extends:
            report.append(f"- `{rel(path)}`")
    else:
        report.append("- none")

    report.append("")

    report.append("### Templates with inline styles")
    report.append("")

    if templates_with_inline_styles:
        for path, style_attrs, style_tags in templates_with_inline_styles:
            report.append(
                f"- `{rel(path)}` — style attrs: {style_attrs}, style tags: {style_tags}"
            )
    else:
        report.append("- none")

    report.append("")

    report.append("## Static references in templates")
    report.append("")

    static_refs = []

    for path in templates:
        text = read_text(path)

        for match in re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]\s*%}", text):
            static_refs.append((path, match))

    report.append("| Template | Static file | Exists |")
    report.append("|---|---|---:|")

    for path, static_path in static_refs:
        exists = (BASE_DIR / "static" / static_path).exists()
        report.append(
            f"| `{rel(path)}` | `{static_path}` | {'yes' if exists else 'NO'} |"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    print("UI audit report created:")
    print(REPORT_PATH)
    print()
    print("Templates:", len(templates))
    print("CSS files:", len(css_files))
    print("JS files:", len(js_files))
    print("Templates without extends:", len(templates_without_extends))
    print("Templates with inline styles:", len(templates_with_inline_styles))


if __name__ == "__main__":
    main()
