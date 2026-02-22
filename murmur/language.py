"""Language codes and locale detection for murmur."""

from __future__ import annotations

import os
from enum import Enum


class Language(str, Enum):
    """Supported language codes.

    Values are the ISO 639-1 (or AssemblyAI variant) language code strings
    that can be passed directly to the transcription backend.
    """

    ENGLISH = "en"
    ENGLISH_AU = "en_au"
    ENGLISH_UK = "en_uk"
    ENGLISH_US = "en_us"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    HINDI = "hi"
    JAPANESE = "ja"
    CHINESE = "zh"
    FINNISH = "fi"
    KOREAN = "ko"
    POLISH = "pl"
    RUSSIAN = "ru"
    TURKISH = "tr"
    UKRAINIAN = "uk"
    VIETNAMESE = "vi"
    AFRIKAANS = "af"
    ALBANIAN = "sq"
    AMHARIC = "am"
    ARABIC = "ar"
    ARMENIAN = "hy"
    ASSAMESE = "as"
    AZERBAIJANI = "az"
    BASHKIR = "ba"
    BASQUE = "eu"
    BELARUSIAN = "be"
    BENGALI = "bn"
    BOSNIAN = "bs"
    BRETON = "br"
    BULGARIAN = "bg"
    BURMESE = "my"
    CATALAN = "ca"
    CROATIAN = "hr"
    CZECH = "cs"
    DANISH = "da"
    ESTONIAN = "et"
    FAROESE = "fo"
    GALICIAN = "gl"
    GEORGIAN = "ka"
    GREEK = "el"
    GUJARATI = "gu"
    HAITIAN = "ht"
    HAUSA = "ha"
    HAWAIIAN = "haw"
    HEBREW = "he"
    HUNGARIAN = "hu"
    ICELANDIC = "is"
    INDONESIAN = "id"
    JAVANESE = "jw"
    KANNADA = "kn"
    KAZAKH = "kk"
    KHMER = "km"
    LAO = "lo"
    LATIN = "la"
    LATVIAN = "lv"
    LINGALA = "ln"
    LITHUANIAN = "lt"
    LUXEMBOURGISH = "lb"
    MACEDONIAN = "mk"
    MALAGASY = "mg"
    MALAY = "ms"
    MALAYALAM = "ml"
    MALTESE = "mt"
    MAORI = "mi"
    MARATHI = "mr"
    MONGOLIAN = "mn"
    NEPALI = "ne"
    NORWEGIAN = "no"
    NORWEGIAN_NYNORSK = "nn"
    OCCITAN = "oc"
    PANJABI = "pa"
    PASHTO = "ps"
    PERSIAN = "fa"
    ROMANIAN = "ro"
    SANSKRIT = "sa"
    SERBIAN = "sr"
    SHONA = "sn"
    SINDHI = "sd"
    SINHALA = "si"
    SLOVAK = "sk"
    SLOVENIAN = "sl"
    SOMALI = "so"
    SUNDANESE = "su"
    SWAHILI = "sw"
    SWEDISH = "sv"
    TAGALOG = "tl"
    TAJIK = "tg"
    TAMIL = "ta"
    TATAR = "tt"
    TELUGU = "te"
    THAI = "th"
    TIBETAN = "bo"
    TURKMEN = "tk"
    URDU = "ur"
    UZBEK = "uz"
    WELSH = "cy"
    YIDDISH = "yi"
    YORUBA = "yo"


# Build a set of valid Language values for fast membership testing.
_VALID_CODES: frozenset[str] = frozenset(lang.value for lang in Language)


def resolve_language(override: str | None = None) -> str | None:
    """Determine the language code to use.

    Resolution order:
    1. ``override`` — if set and non-empty, return it as-is.
    2. ``$LC_ALL`` then ``$LANG`` — parse e.g. ``de_DE.UTF-8`` to ``de``;
       if the result maps to a known Language value, return it.
    3. ``None`` — caller should fall back to its own default (usually ``"en"``).
    """
    if override:
        return override

    for env_var in ("LC_ALL", "LANG"):
        locale = os.environ.get(env_var, "")
        if not locale:
            continue
        # Strip encoding suffix (e.g. ".UTF-8") then take the language part
        # before the territory separator "_".
        code = locale.split(".")[0].split("_")[0].lower()
        if code in _VALID_CODES:
            return code

    return None


def to_assemblyai(language_code: str) -> str:
    """Return the language code string to pass to AssemblyAI StreamingParameters.

    AssemblyAI currently uses the same ISO 639-1 codes (and regional variants
    like ``"en_au"``) as the Language enum values, so this is effectively an
    identity function.  The abstraction exists so that future provider
    differences can be handled here without touching call sites.

    If ``language_code`` is not a recognised Language value, it is returned
    unchanged (passthrough).
    """
    return language_code
