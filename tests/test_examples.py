import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / '.agents/skills'
SUMMARY = SKILLS / 'repo-change-summary/scripts/summarize.py'
CHECK = SKILLS / 'check-learning-project/scripts/check_project.py'
VALIDATE = ROOT / 'tools/validate_skills.py'


def cli(script, *args):
    return subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                          capture_output=True, text=True)


class ExampleTests(unittest.TestCase):
    def setUp(self):
        # Системная временная папка: внутри клона git нашёл бы родительский репозиторий.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def git(self, *args):
        result = subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c',
                                 'core.hooksPath=' + str(self.work / '.git/hooks'),
                                 '-C', str(self.work), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def repository(self):
        self.git('init', '-q', '--template=')
        self.git('config', 'user.name', 'Example Author')
        self.git('config', 'user.email', 'example@example.invalid')
        (self.work / 'main.py').write_text('print(1)\n')
        (self.work / 'README.md').write_text('Учебный проект\n')
        self.git('add', 'main.py', 'README.md')
        self.git('commit', '-qm', 'Учебная основа')

    def test_summary_separates_staged_unstaged_and_untracked(self):
        self.repository()
        (self.work / 'main.py').write_text('print(2)\n')
        self.git('add', 'main.py')
        (self.work / 'main.py').write_text('print(3)\n')
        (self.work / 'README.md').write_text('Учебный проект: обновлено\n')
        (self.work / 'new note.txt').write_text('Новая заметка\n')
        result = cli(SUMMARY, '--repo', self.work)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['staged'], [{'status': 'M', 'path': 'main.py'}])
        self.assertEqual(data['unstaged'], [{'status': 'M', 'path': 'README.md'},
                                             {'status': 'M', 'path': 'main.py'}])
        self.assertEqual(data['untracked'], ['new note.txt'])
        self.assertEqual(data['checks'], 'не запускались')

    def test_summary_clean_repository(self):
        self.repository()
        result = cli(SUMMARY, '--repo', self.work)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual([data['staged'], data['unstaged'], data['untracked']], [[], [], []])

    def test_summary_preserves_newline_in_filename(self):
        self.repository()
        (self.work / 'new\nnote.txt').write_text('note\n')
        result = cli(SUMMARY, '--repo', self.work)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['untracked'], ['new\nnote.txt'])

    def test_summary_does_not_write_index_or_files(self):
        self.repository()
        before = (self.work / '.git/index').read_bytes()
        content = (self.work / 'main.py').read_bytes()
        self.assertEqual(cli(SUMMARY, '--repo', self.work).returncode, 0)
        self.assertEqual((self.work / '.git/index').read_bytes(), before)
        self.assertEqual((self.work / 'main.py').read_bytes(), content)

    def test_summary_rejects_non_repository(self):
        result = cli(SUMMARY, '--repo', self.work)
        self.assertEqual(result.returncode, 2)
        self.assertIn('репозитор', result.stderr)

    def test_summary_rejects_unborn_head(self):
        self.git('init', '-q')
        result = cli(SUMMARY, '--repo', self.work)
        self.assertEqual(result.returncode, 2)
        self.assertIn('коммит', result.stderr)

    def test_project_good_fixture_matches_expected(self):
        result = cli(CHECK, '--project', ROOT / 'fixtures/project-good')
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = json.loads((ROOT / 'fixtures/expected-project-good.json').read_text())
        self.assertEqual(json.loads(result.stdout), expected)

    def test_project_bad_fixture_reports_failures(self):
        result = cli(CHECK, '--project', ROOT / 'fixtures/project-broken')
        self.assertEqual(result.returncode, 1)
        expected = json.loads((ROOT / 'fixtures/expected-project-broken.json').read_text())
        self.assertEqual(json.loads(result.stdout), expected)

    def test_project_does_not_execute_python(self):
        (self.work / 'project.json').write_text('{"title":"Example", "entry":"main.py"}')
        (self.work / 'README.md').write_text('Учебное описание\n')
        (self.work / 'tests').mkdir()
        (self.work / 'tests/test_main.py').write_text('raise RuntimeError("do not execute")\n')
        marker = self.work / 'SHOULD_NOT_EXIST'
        (self.work / 'main.py').write_text('from pathlib import Path\nPath("SHOULD_NOT_EXIST").write_text("bad")\n')
        result = cli(CHECK, '--project', self.work)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_project_rejects_entry_escape(self):
        (self.work / 'project.json').write_text('{"title":"Example", "entry":"../main.py"}')
        result = cli(CHECK, '--project', self.work)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['checks']['entry'])

    def test_project_rejects_symlink_entry(self):
        (self.work / 'project.json').write_text('{"title":"Example", "entry":"main.py"}')
        (self.work / 'source.py').write_text('pass\n')
        (self.work / 'main.py').symlink_to(self.work / 'source.py')
        result = cli(CHECK, '--project', self.work)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['checks']['entry'])

    def test_project_missing_manifest_is_clear_failure(self):
        result = cli(CHECK, '--project', self.work)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['checks']['manifest'])

    def test_validate_both_shipped_skills(self):
        result = cli(VALIDATE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK repo-change-summary', result.stdout)
        self.assertIn('OK check-learning-project', result.stdout)

    def make_skill(self, text, name='demo'):
        path = self.work / name
        path.mkdir(exist_ok=True)
        (path / 'SKILL.md').write_text(text)
        return path

    def test_validator_missing_description(self):
        path = self.make_skill('---\nname: demo\n---\n# Действие\n')
        result = cli(VALIDATE, path)
        self.assertEqual(result.returncode, 1)
        self.assertIn('description', result.stdout)

    def test_validator_duplicate_key(self):
        path = self.make_skill('---\nname: demo\nname: other\ndescription: Check\n---\nBody\n')
        result = cli(VALIDATE, path)
        self.assertEqual(result.returncode, 1)
        self.assertIn('повторяется', result.stdout)

    def test_validator_empty_body(self):
        path = self.make_skill('---\nname: demo\ndescription: Check\n---\n')
        result = cli(VALIDATE, path)
        self.assertEqual(result.returncode, 1)
        self.assertIn('инструкц', result.stdout)

    def test_validator_name_mismatch(self):
        path = self.make_skill('---\nname: other\ndescription: Check\n---\nBody\n')
        result = cli(VALIDATE, path)
        self.assertEqual(result.returncode, 1)
        self.assertIn('name', result.stdout)

    def test_free_demo_matches_expected(self):
        result = cli(ROOT / 'examples/demo.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = json.loads((ROOT / 'fixtures/expected-demo.json').read_text())
        self.assertEqual(json.loads(result.stdout), expected)

    def test_demo_does_not_require_git_signing(self):
        env = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='commit.gpgsign',
                   GIT_CONFIG_VALUE_0='true', GIT_CONFIG_KEY_1='', GIT_CONFIG_VALUE_1='')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'examples/demo.py')],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
