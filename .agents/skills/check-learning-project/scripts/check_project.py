"""Статическая проверка маленького учебного Python-проекта, без запуска кода."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys

MAX_BYTES = 1024 * 1024
MAX_FILES = 200


def read_text(path):
    if path.is_symlink():
        raise ValueError('Ссылки не проверяются')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Файл больше 1 МиБ')
    return data.decode('utf-8')


def safe_entry(root, value):
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or path.suffix != '.py':
        return False
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            return False
    return current.is_file()


def check_project(root):
    checks = dict.fromkeys(('manifest', 'entry', 'readme', 'tests_present', 'python_syntax'), False)
    try:
        manifest = json.loads(read_text(root / 'project.json'))
        if isinstance(manifest, dict):
            checks['manifest'] = isinstance(manifest.get('title'), str) and bool(manifest['title'].strip())
            checks['entry'] = safe_entry(root, manifest.get('entry'))
    except (OSError, ValueError):
        pass
    try:
        checks['readme'] = bool(read_text(root / 'README.md').strip())
    except (OSError, ValueError):
        pass
    syntax_ok, python_files = True, 0
    def walk_error(_error):
        nonlocal syntax_ok
        syntax_ok = False
    for folder, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs[:]:
            if name.startswith('.'):
                dirs.remove(name)
            elif (Path(folder) / name).is_symlink():
                syntax_ok = False
                dirs.remove(name)
        for name in sorted(files):
            if not name.endswith('.py'):
                continue
            python_files += 1
            if python_files > MAX_FILES:
                syntax_ok = False
                break
            path = Path(folder) / name
            try:
                ast.parse(read_text(path), filename=path.relative_to(root).as_posix())
                if path.relative_to(root).parts[0] == 'tests' and name.startswith('test_'):
                    checks['tests_present'] = True
            except (OSError, ValueError, SyntaxError, RecursionError):
                syntax_ok = False
        if python_files > MAX_FILES:
            break
    checks['python_syntax'] = syntax_ok and python_files > 0
    return {'ok': all(checks.values()), 'checks': checks,
            'limits': ['Проверка статическая: код и тесты не запускались']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    if args.project.is_symlink() or not args.project.is_dir():
        print('Укажите существующую папку учебного проекта без символической ссылки', file=sys.stderr)
        return 2
    result = check_project(args.project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
