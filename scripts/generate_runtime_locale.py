"""Generate domains/runtime_locale.lua: HD2Runtime's own on-screen text in the game's languages (0.31.1, runtime/i18n.lua).

Source: schemas/runtime_locale.json
  languages  the game languages in the order the F10 panel lists them: {code, name} (each name in its own language);
             the codes are the game's own (runtime/text_resources.lua, domains/text_resources.lua languages)
  fallback   {code: code}: the language a missing translation is taken from first (English last)
  strings    {English source: {code: translation}}

Checks (the generator refuses to write otherwise):
  * every language code is one of the game's; every translation names a known code and is non-empty;
  * every translation has exactly the source's format specifiers, in the same order (string.format cannot reorder);
  * the strings are exactly the English sources the Runtime shows (sources(): the literals passed to i18n.t / T /
    both in runtime/ and api/, and the tables shown by reference): none missing, none stale.

  py scripts/generate_runtime_locale.py           # write
  py scripts/generate_runtime_locale.py --check   # fail when stale
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'schemas/runtime_locale.json'
OUTPUT = ROOT / 'domains/runtime_locale.lua'
GAME_LANGUAGES = ('us', 'gb', 'bp', 'de', 'es', 'fr', 'it', 'jp', 'ko', 'ms', 'pl', 'pt', 'ru', 'cn', 'tc')
SPEC = re.compile(r'%(?:%|[-+ #0]*\d*(?:\.\d+)?[a-zA-Z])')
LIT = r"""(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")"""


def specifiers(text):
    return [m for m in SPEC.findall(text) if m != '%%']


def _unescape(s):
    return s.replace("\\'", "'").replace('\\"', '"')


def sources():
    """The English texts the Runtime translates, in a stable order."""
    out = []

    def add(s):
        if s not in out:
            out.append(s)

    for path in sorted((ROOT / 'runtime').glob('*.lua')) + sorted((ROOT / 'api').glob('*.lua')):
        text = path.read_text(encoding='utf-8')
        for m in re.finditer(r"(?:\bT|\.t|\bboth)\(\s*" + LIT, text):
            add(_unescape(m.group(1) if m.group(1) is not None else m.group(2)))
    custom = (ROOT / 'runtime/custom_stratagems.lua').read_text(encoding='utf-8')
    for m in re.finditer(r"same_mods='((?:[^'\\]|\\.)*)'", custom):
        add(_unescape(m.group(1)))
    for rel, pattern in (('runtime/runtime_settings.lua', r"(?:label|description)='((?:[^'\\]|\\.)*)'"),
                         ('runtime/init_progress.lua', r"label='((?:[^'\\]|\\.)*)',weight")):
        for m in re.finditer(pattern, (ROOT / rel).read_text(encoding='utf-8')):
            add(_unescape(m.group(1)))
    safety = (ROOT / 'runtime/matchmaking_safety.lua').read_text(encoding='utf-8')
    block = safety[safety.index('M.TEXT={'):safety.index('\n}', safety.index('M.TEXT={'))]
    for m in re.finditer(r"=\s*'((?:[^'\\]|\\.)*)'", block):
        add(_unescape(m.group(1)))
    line = safety[safety.index('M.NAMES='):safety.index('\n', safety.index('M.NAMES='))]
    for m in re.finditer(r"='([^']*)'", line):
        add(m.group(1))
    for rel in ('runtime/beam_conversion_sync.lua', 'runtime/beam_conversion_watch.lua'):
        text = (ROOT / rel).read_text(encoding='utf-8')
        start = text.index('NOTICE={') if 'NOTICE={' in text else text.index('M.TEXT={')
        block = text[start:text.index("'}", start) + 2]
        for m in re.finditer(r"(\w+)='((?:[^'\\]|\\.)*)'((?:\s*\.\.'(?:[^'\\]|\\.)*')*)", block):
            add(_unescape(m.group(2) + ''.join(re.findall(r"\.\.'((?:[^'\\]|\\.)*)'", m.group(3)))))
    for key in ('M.KIND_TRAITS={', 'M.CATEGORIES={'):
        block = custom[custom.index(key):custom.index('}', custom.index(key))]
        for m in re.finditer(r"='([^']*)'", block):
            add(m.group(1))
    panel = (ROOT / 'runtime/custom_stratagem_panel.lua').read_text(encoding='utf-8')
    add(re.search(r"M\.TITLE='([^']*)'", panel).group(1))
    for m in re.finditer(r"title='([^']*)'", panel):
        add(m.group(1))
    return out


def lua(value):
    if isinstance(value, dict):
        return '{' + ','.join('[' + lua(k) + ']=' + lua(v) for k, v in sorted(value.items())) + '}'
    if isinstance(value, list):
        return '{' + ','.join(lua(v) for v in value) + '}'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return 'nil'
    if isinstance(value, (int, float)):
        return repr(value)
    # A Lua string: the UTF-8 bytes, every byte outside printable ASCII as a decimal escape (Lua 5.1 has no \u).
    out = []
    for byte in str(value).encode('utf-8'):
        ch = chr(byte)
        if ch in '\\"':
            out.append('\\' + ch)
        elif 32 <= byte < 127:
            out.append(ch)
        else:
            out.append('\\%d' % byte)
    return '"' + ''.join(out) + '"'


def build():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    languages = data['languages']
    codes = [item['code'] for item in languages]
    assert sorted(codes) == sorted(GAME_LANGUAGES), 'the languages must be the game languages: ' + repr(codes)
    for code, other in data['fallback'].items():
        assert code in codes and other in codes and code != other, (code, other)
    expected = sources()
    strings = data['strings']
    missing = [s for s in expected if s not in strings]
    stale = [s for s in strings if s not in expected]
    assert not missing, 'sources without an entry in schemas/runtime_locale.json: ' + repr(missing)
    assert not stale, 'entries no Runtime text uses any more: ' + repr(stale)
    out = {}
    for source in expected:
        entry = strings[source]
        want = specifiers(source)
        clean = {}
        for code, text in entry.items():
            assert code in codes and code != 'us', (source, code)
            assert isinstance(text, str) and text.strip(), (source, code, 'empty')
            assert '\n' not in text, (source, code, 'a line break')
            got = specifiers(text)
            assert got == want, f'{code}: {text!r} has the specifiers {got}, the source {source!r} {want}'
            clean[code] = text
        out[source] = clean
    return {'languages': languages, 'fallback': data['fallback'], 'strings': out}


def render(value):
    return ('-- Generated from schemas/runtime_locale.json by scripts/generate_runtime_locale.py; do not edit.\n'
            '-- HD2Runtime\'s own on-screen text in the game\'s languages (runtime/i18n.lua).\nreturn ' + lua(value) + '\n')


def generate(check=False):
    body = render(build())
    if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == body:
        return False
    if check:
        raise RuntimeError('Stale runtime locale output: ' + str(OUTPUT))
    OUTPUT.write_text(body, encoding='utf-8', newline='\n')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(str(OUTPUT) if generate(args.check) else 'up to date')
