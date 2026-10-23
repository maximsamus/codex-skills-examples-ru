"""Список локальных изменений Git. Содержимое файлов не читается."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    result = subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                             '-C', str(repo), *args], capture_output=True, env=env)
    if result.returncode:
        raise ValueError('Не удалось прочитать репозиторий; проверьте путь, наличие первого коммита и состояние Git')
    return result.stdout


def changes(raw):
    parts = raw.split(b'\0')
    if parts[-1] != b'' or (len(parts) - 1) % 2:
        raise ValueError('Git вернул неполный список изменений')
    return [{'status': parts[index].decode('ascii'), 'path': os.fsdecode(parts[index + 1])}
            for index in range(0, len(parts) - 1, 2)]


def summarize(repo):
    root = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip())
    git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    options = ('--no-ext-diff', '--no-textconv', '--no-renames', '--name-status', '-z')
    return {
        'staged': changes(git(root, 'diff', *options, '--cached', 'HEAD', '--')),
        'unstaged': changes(git(root, 'diff', *options, '--')),
        'untracked': [os.fsdecode(item) for item in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if item],
        'checks': 'не запускались',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        result = summarize(args.repo)
    except (OSError, ValueError) as error:
        message = str(error) if isinstance(error, ValueError) else 'Не удалось запустить Git; проверьте его установку и путь к репозиторию'
        print(message, file=sys.stderr)
        return 2
    # ASCII-экранирование сохраняет даже имена файлов с нестандартными байтами.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
