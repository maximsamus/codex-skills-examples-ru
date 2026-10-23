"""Проверить формат SKILL.md в двух примерах этого репозитория."""
import argparse
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from frontmatter import FrontmatterError, parse

ROOT = Path(__file__).resolve().parents[1]


def validate(folder):
    path = folder / 'SKILL.md'
    try:
        if folder.is_symlink() or path.is_symlink():
            raise ValueError('Ссылки не проверяются')
        with path.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('SKILL.md больше 1 МиБ')
        fields, body = parse(raw.decode('utf-8'))
        if fields.get('name') != folder.name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', folder.name) or len(folder.name) > 64:
            raise ValueError('name должен совпадать с папкой: строчные латинские буквы, цифры и дефисы, до 64 знаков')
        if not fields.get('description', '').strip():
            raise ValueError('Добавьте непустой description')
        if not body:
            raise ValueError('Добавьте инструкции после frontmatter')
    except (FrontmatterError, ValueError, OSError) as error:
        message = str(error) if isinstance(error, ValueError) else 'Не удалось прочитать SKILL.md'
        return 'ERROR {}: {}'.format(folder.name, message)
    return 'OK {}: SKILL.md проверен'.format(folder.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders', type=Path, nargs='*')
    args = parser.parse_args()
    folders = args.folders or sorted((ROOT / '.agents/skills').iterdir())
    rows = [validate(folder) for folder in folders]
    if not rows:
        print('ERROR: навыки не найдены')
        return 1
    print('\n'.join(rows))
    return 0 if all(row.startswith('OK ') for row in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
