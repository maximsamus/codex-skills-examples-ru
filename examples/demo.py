"""Два воспроизводимых примера без Codex и подписки."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main():
    (ROOT / '.test-tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.test-tmp') as temporary:
        repo = Path(temporary)
        def git(*args):
            return command(['git', '-c', 'commit.gpgsign=false', '-c',
                            'core.hooksPath=' + str(repo / '.git/hooks'), '-C', str(repo), *args])
        git('init', '-q', '--template=')
        git('config', 'user.name', 'Example Author')
        git('config', 'user.email', 'example@example.invalid')
        (repo / 'main.py').write_text('print(1)\n')
        (repo / 'README.md').write_text('Учебный проект\n')
        git('add', 'main.py', 'README.md')
        git('commit', '-qm', 'Учебная основа')
        (repo / 'main.py').write_text('print(2)\n')
        git('add', 'main.py')
        (repo / 'README.md').write_text('Обновленное описание\n')
        (repo / 'notes.txt').write_text('Новая заметка\n')
        summary = command([sys.executable, '-B', str(ROOT / '.agents/skills/repo-change-summary/scripts/summarize.py'), '--repo', str(repo)])
    project = command([sys.executable, '-B', str(ROOT / '.agents/skills/check-learning-project/scripts/check_project.py'), '--project', str(ROOT / 'fixtures/project-good')])
    print(json.dumps({'summary': json.loads(summary), 'project': json.loads(project)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
