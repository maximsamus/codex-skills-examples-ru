"""Небольшой читающий разборщик документированного подмножества YAML.

Поддерживает строковые поля и блоки |/>. Сложный YAML явно отклоняется,
а не объявляется невалидным для Claude Code.
"""
import json
import re


class FrontmatterError(ValueError):
    code = 'E_FRONTMATTER'


class UnsupportedYaml(FrontmatterError):
    code = 'E_UNSUPPORTED_YAML'


def scalar(value, string_required=True):
    value = value.strip()
    if value.startswith('"'):
        try:
            result, end = json.JSONDecoder().raw_decode(value)
        except ValueError:
            raise FrontmatterError('Проверьте двойные кавычки и экранирование строки') from None
        rest = value[end:].strip()
        if not isinstance(result, str) or (rest and not rest.startswith('#')):
            raise FrontmatterError('После строки допустим только комментарий')
        return result
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if not match:
            raise FrontmatterError('Проверьте одинарные кавычки строки')
        return match.group(1).replace("''", "'")
    value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
    if not value or value.startswith('#'):
        return ''
    if value[0] in '%@`],}|>' or value.startswith('? '):
        raise FrontmatterError('Недопустимое начало строки YAML; заключите текст в кавычки')
    if value[0] in '[{&*!' or ': ' in value or value.startswith('- '):
        raise UnsupportedYaml('Эта форма YAML не поддерживается; используйте строку в кавычках или проверьте YAML отдельно')
    if string_required and (value.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', 'null', '~') or re.fullmatch(r'[-+]?\d+(?:\.\d+)?', value)):
        raise FrontmatterError('В этом профиле поля должны быть строками, заключите значение в кавычки')
    return value


def parse(text):
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise FrontmatterError('Начните SKILL.md со строки ---')
    try:
        end = lines.index('---', 1)
    except ValueError:
        raise FrontmatterError('Нет закрывающей строки ---') from None
    fields = {}
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([a-z][a-z0-9_-]*):(?:\s+(.*))?', line)
        if not match:
            if line.startswith((' ', '\t')):
                raise UnsupportedYaml('Вложенный YAML не поддерживается; проверьте его отдельно')
            raise FrontmatterError('Ожидается поле вида name: значение')
        key, value = match.group(1), match.group(2) or ''
        if key in fields:
            raise FrontmatterError('Поле повторяется: ' + key)
        if value in ('|', '|-', '|+', '>', '>-', '>+'):
            block = []
            while index < end and (not lines[index].strip() or lines[index].startswith('  ')):
                block.append(lines[index].strip())
                index += 1
            fields[key] = (' ' if value.startswith('>') else '\n').join(block).strip()
        else:
            fields[key] = scalar(value, string_required=key in ('name', 'description'))
    return fields, '\n'.join(lines[end + 1:]).strip()
