import json
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "lanwatch" / "static"
LOCALES = STATIC / "locales"
REFERENCE = "en"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def flatten(node: dict[str, object], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat |= flatten(value, f"{path}.")
        else:
            flat[path] = str(value)
    return flat


def catalog(lang: str) -> dict[str, str]:
    return flatten(json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")))


LANGUAGES = sorted(path.stem for path in LOCALES.glob("*.json"))


def test_reference_language_exists() -> None:
    assert REFERENCE in LANGUAGES
    assert len(LANGUAGES) > 1


@pytest.mark.parametrize("lang", [lang for lang in LANGUAGES if lang != REFERENCE])
def test_translation_matches_reference(lang: str) -> None:
    reference, translation = catalog(REFERENCE), catalog(lang)
    assert sorted(set(reference) - set(translation)) == [], "missing keys"
    assert sorted(set(translation) - set(reference)) == [], "unknown keys"
    for key, text in reference.items():
        assert set(PLACEHOLDER.findall(translation[key])) == set(PLACEHOLDER.findall(text)), key
        assert translation[key].strip(), key


def test_static_keys_used_by_the_ui_exist() -> None:
    sources = [(STATIC / "index.html").read_text(encoding="utf-8")]
    sources += [path.read_text(encoding="utf-8") for path in (STATIC / "js").glob("*.js")]
    used = set()
    for source in sources:
        used |= set(re.findall(r'data-i18n(?:-placeholder|-aria)?="([\w.]+)"', source))
        used |= set(re.findall(r"\bth?\('([\w.]+)'", source))
    assert sorted(used - set(catalog(REFERENCE))) == []
