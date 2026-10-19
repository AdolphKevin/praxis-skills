"""Small, line-aware YAML reader. No anchors, tags, block scalars or documents."""
from __future__ import annotations

import re


class YamlError(ValueError):
    def __init__(self, message, line):
        super().__init__(message)
        self.lineno = line


class Mapping(dict):
    def __init__(self, line):
        super().__init__()
        self.line = line
        self.lines = {}


class Sequence(list):
    def __init__(self, line):
        super().__init__()
        self.line = line


def uncomment(text):
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == '\\' and quote == '"':
                i += 2
                continue
            if char == quote:
                if quote == "'" and text[i:i + 2] == "''":
                    i += 2
                    continue
                quote = None
        elif char in "\"'" and (i == 0 or text[i - 1] in ' [{,:\t'):
            quote = char
        elif char == '#' and (i == 0 or text[i - 1].isspace()):
            return text[:i].rstrip()
        i += 1
    return text.rstrip()


def split_pair(text):
    quote, depth, i = None, 0, 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == '\\' and quote == '"':
                i += 2
                continue
            if char == quote:
                if quote == "'" and text[i:i + 2] == "''":
                    i += 2
                    continue
                quote = None
        elif char in "\"'" and (i == 0 or text[i - 1] in ' [{,:\t'):
            quote = char
        elif char in '[{':
            depth += 1
        elif char in ']}':
            depth -= 1
        elif char == ':' and depth == 0 and (i + 1 == len(text) or text[i + 1].isspace()):
            return text[:i], text[i + 1:].lstrip()
        i += 1
    return None


def fold(text):
    # One physical break folds to a space; each intervening empty line adds a break.
    return re.sub(r'[ \t]*\n([ \t]*\n)*[ \t]*',
                  lambda m: ' ' if m.group().count('\n') == 1
                  else '\n' * (m.group().count('\n') - 1), text)


class Flow:
    def __init__(self, text, line):
        self.text, self.start, self.i = text, line, 0

    def line(self):
        return self.start + self.text[:self.i].count('\n')

    def fail(self, message):
        raise YamlError(message, self.line())

    def space(self):
        while self.i < len(self.text):
            if self.text[self.i].isspace():
                self.i += 1
            elif self.text[self.i] == '#':
                end = self.text.find('\n', self.i)
                self.i = len(self.text) if end < 0 else end
            else:
                break

    def quoted(self):
        quote = self.text[self.i]
        self.i += 1
        output = []
        escapes = {'0': '\0', 'a': '\a', 'b': '\b', 't': '\t', 'n': '\n',
                   'v': '\v', 'f': '\f', 'r': '\r', 'e': '\x1b', ' ': ' ',
                   '"': '"', '/': '/', '\\': '\\', 'N': '\x85', '_': '\xa0',
                   'L': '\u2028', 'P': '\u2029'}
        while self.i < len(self.text):
            char = self.text[self.i]
            self.i += 1
            if char == quote:
                if quote == "'" and self.text[self.i:self.i + 1] == "'":
                    output.append("'")
                    self.i += 1
                else:
                    return ''.join(output)
            elif char == '\\' and quote == '"':
                if self.i == len(self.text):
                    self.fail('未结束的转义')
                escape = self.text[self.i]
                self.i += 1
                if escape == '\n':
                    while self.i < len(self.text) and self.text[self.i] in ' \t':
                        self.i += 1
                elif escape in 'xuU':
                    width = {'x': 2, 'u': 4, 'U': 8}[escape]
                    value = self.text[self.i:self.i + width]
                    if len(value) != width or not re.fullmatch(r'[0-9a-fA-F]+', value):
                        self.fail('不合法的 Unicode 转义')
                    try:
                        output.append(chr(int(value, 16)))
                    except ValueError:
                        self.fail('不合法的 Unicode 字符')
                    self.i += width
                elif escape in escapes:
                    output.append(escapes[escape])
                else:
                    self.fail(f'不支持的转义 \\{escape}')
            elif char == '\n':
                while output and output[-1] in (' ', '\t'):
                    output.pop()
                breaks = 1
                while self.i < len(self.text) and self.text[self.i].isspace():
                    breaks += self.text[self.i] == '\n'
                    self.i += 1
                output.append(' ' if breaks == 1 else '\n' * (breaks - 1))
            else:
                output.append(char)
        self.fail('引号字符串没有结束')

    def value(self, key=False, in_flow=False):
        self.space()
        if self.i >= len(self.text):
            return None
        char = self.text[self.i]
        line = self.line()
        if char in '&*!|>':
            self.fail('不支持锚点、别名、标签或块标量')
        if char in "\"'":
            return self.quoted()
        if char in '[{':
            self.i += 1
            mapping = char == '{'
            end = '}' if mapping else ']'
            result = Mapping(line) if mapping else Sequence(line)
            self.space()
            if self.text[self.i:self.i + 1] == end:
                self.i += 1
                return result
            while True:
                item_line = self.line()
                item = self.value(key=mapping, in_flow=True)
                if mapping:
                    if not isinstance(item, str):
                        self.fail('对象的键必须是字符串')
                    self.space()
                    if self.text[self.i:self.i + 1] != ':':
                        self.fail('对象缺少冒号')
                    self.i += 1
                    if item in result:
                        self.fail(f'重复字段 {item}')
                    result[item] = self.value(in_flow=True)
                    result.lines[item] = item_line
                else:
                    result.append(item)
                self.space()
                char = self.text[self.i:self.i + 1]
                if char == end:
                    self.i += 1
                    return result
                if char != ',':
                    self.fail(f'流样式缺少逗号或 {end}')
                self.i += 1
                self.space()
                if self.text[self.i:self.i + 1] == end:
                    self.i += 1
                    return result
        start = self.i
        while self.i < len(self.text):
            char = self.text[self.i]
            if (in_flow and char in ',]}') or (key and char == ':'):
                break
            if char == '#' and (self.i == start or self.text[self.i - 1].isspace()):
                break
            self.i += 1
        raw = fold(self.text[start:self.i].strip())
        if not raw:
            self.fail('缺少值')
        if raw in ('null', 'Null', 'NULL', '~'):
            return None
        if raw.lower() in ('true', 'false', 'yes', 'no', 'on', 'off'):
            return raw.lower() in ('true', 'yes', 'on')
        number = raw.replace('_', '')
        if re.fullmatch(r'[-+]?\d+', number):
            return int(number)
        if re.fullmatch(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?', number):
            return float(number)
        return raw

    def parse(self):
        value = self.value()
        self.space()
        if self.i != len(self.text):
            self.fail('值之后有多余内容')
        return value


class Reader:
    def __init__(self, text):
        self.lines = text.replace('\r\n', '\n').replace('\r', '\n').splitlines()
        self.i = 0
        self.comments = []

    def skip(self):
        while self.i < len(self.lines) and not uncomment(self.lines[self.i]).strip():
            if self.lines[self.i].lstrip().startswith('#'):
                self.comments.append((self.i + 1, self.lines[self.i]))
            self.i += 1

    def current(self):
        raw = self.lines[self.i]
        if '\t' in raw[:len(raw) - len(raw.lstrip())]:
            raise YamlError('缩进不能使用制表符', self.i + 1)
        return len(raw) - len(raw.lstrip(' ')), uncomment(raw).lstrip(' ')

    def scalar(self, first, indent, line):
        # Accumulate physical continuation lines before parsing quotes/flow structures.
        chunks = [first]
        quote, depth = None, 0
        def open_value():
            nonlocal quote, depth
            if first[:1] not in ('[', '{', chr(34), chr(39)):
                return False
            quote, depth, j = None, 0, 0
            joined = '\n'.join(chunks)
            while j < len(joined):
                c = joined[j]
                if quote:
                    if c == '\\' and quote == '"':
                        j += 2
                        continue
                    if c == quote:
                        if quote == "'" and joined[j:j + 2] == "''":
                            j += 2
                            continue
                        quote = None
                elif c in "\"'" and (j == 0 or joined[j - 1] in ' [{,:\n\t'):
                    quote = c
                elif c == '#' and (j == 0 or joined[j - 1].isspace()):
                    end = joined.find('\n', j)
                    if end < 0:
                        break
                    j = end
                elif c in '[{':
                    depth += 1
                elif c in ']}':
                    depth -= 1
                j += 1
            return quote is not None or depth > 0
        while self.i < len(self.lines):
            opened = open_value()
            raw = self.lines[self.i]
            if quote is None and raw.lstrip().startswith('#'):
                self.comments.append((self.i + 1, raw))
            if not raw.strip() or (not opened and raw.lstrip().startswith('#')):
                if not raw.strip():
                    chunks.append('')
                self.i += 1
                continue
            next_indent, next_text = self.current()
            if opened:
                chunks.append(raw if quote else next_text)
                self.i += 1
            elif next_indent > indent:
                if split_pair(next_text) or next_text.startswith('- '):
                    raise YamlError('标量之后出现了意外的缩进', self.i + 1)
                chunks.append(next_text)
                self.i += 1
            else:
                break
        return Flow('\n'.join(chunks).rstrip(), line).parse()

    def child(self, value, parent_indent, line):
        if value:
            return self.scalar(value, parent_indent, line)
        self.skip()
        if self.i < len(self.lines):
            indent, content = self.current()
            if indent > parent_indent or (indent == parent_indent and
                                          (content == '-' or content.startswith('- '))):
                return self.block(indent)
        return None

    def pair(self, result, content, indent, line):
        pair = split_pair(content)
        if pair is None:
            raise YamlError('对象字段缺少冒号', line)
        key, value = pair
        key = Flow(key.strip(), line).parse()
        if not isinstance(key, str) or not key:
            raise YamlError('对象的键必须是非空字符串', line)
        if key in result:
            raise YamlError(f'重复字段 {key}', line)
        result.lines[key] = line
        result[key] = self.child(value, indent, line)

    def item(self, value, indent, line):
        if value == '-' or value.startswith('- '):
            nested = Sequence(line)
            nested.append(self.item(value[1:].lstrip(), indent + 2, line))
            self.skip()
            if self.i < len(self.lines):
                next_indent, next_text = self.current()
                if next_indent == indent + 2 and (next_text == '-' or next_text.startswith('- ')):
                    nested.extend(self.block(indent + 2))
            return nested
        if split_pair(value):
            item = Mapping(line)
            self.pair(item, value, indent + 2, line)
            while self.i < len(self.lines):
                self.skip()
                if self.i == len(self.lines):
                    break
                child_indent, child_text = self.current()
                if child_indent <= indent:
                    break
                if child_indent != indent + 2:
                    raise YamlError('不合法的数组对象缩进', self.i + 1)
                child_line = self.i + 1
                self.i += 1
                self.pair(item, child_text, indent + 2, child_line)
            return item
        return self.child(value, indent, line)

    def block(self, indent):
        self.skip()
        _, first = self.current()
        sequence = first == '-' or first.startswith('- ')
        result = Sequence(self.i + 1) if sequence else Mapping(self.i + 1)
        if not sequence and split_pair(first) is None:
            line = self.i + 1
            self.i += 1
            return self.scalar(first, indent, line)
        while self.i < len(self.lines):
            self.skip()
            if self.i == len(self.lines):
                break
            current_indent, content = self.current()
            if current_indent < indent:
                break
            if current_indent != indent:
                raise YamlError('不合法的缩进', self.i + 1)
            is_item = content == '-' or content.startswith('- ')
            if sequence != is_item:
                break
            line = self.i + 1
            self.i += 1
            if not sequence:
                self.pair(result, content, indent, line)
                continue
            value = content[1:].lstrip()
            result.append(self.item(value, indent, line))
        return result

    def parse(self):
        self.skip()
        if self.i == len(self.lines):
            return None
        if self.lines[self.i].strip() == '---':
            self.i += 1
            self.skip()
        if self.i == len(self.lines):
            return None
        indent, _ = self.current()
        result = self.block(indent)
        self.skip()
        if self.i < len(self.lines) and self.lines[self.i].strip() == '...':
            self.i += 1
            self.skip()
        if self.i < len(self.lines):
            raise YamlError('不支持多文档或意外内容', self.i + 1)
        return result


def loads(text):
    return Reader(text).parse()


def comment_lines(text):
    reader = Reader(text)
    reader.parse()
    return reader.comments
