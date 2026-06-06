"""
Service untuk menerjemahkan query user ke berbagai bahasa.
Menggunakan deep-translator (Google Translate free, tanpa API key).
Hanya dipakai untuk membantu BM25 retrieval agar lintas bahasa.
"""

from deep_translator import GoogleTranslator
from loguru import logger
from typing import List

# Cache terjemahan agar tidak request berulang untuk query yang sama
_translation_cache: dict = {}

# Bahasa target yang didukung untuk ekspansi query BM25
# id = Indonesia, en = Inggris
SUPPORTED_LANGUAGES = ["id", "en"]


def _get_translator(target: str) -> GoogleTranslator:
    """Buat instance translator dengan source=auto."""
    return GoogleTranslator(source="auto", target=target)


def detect_and_translate(text: str, target: str) -> str | None:
    """
    Terjemahkan text ke bahasa target.
    - Jika text sudah dalam bahasa target, return None (tidak perlu translate).
    - Gunakan cache untuk menghindari request redundant.
    """
    cache_key = f"{text}:{target}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    try:
        translator = _get_translator(target)
        result = translator.translate(text)

        # Jika hasil translate sama persis dengan input, berarti sudah dalam bahasa target
        if result and result.strip().lower() == text.strip().lower():
            _translation_cache[cache_key] = None
            return None

        _translation_cache[cache_key] = result
        return result
    except Exception as e:
        logger.warning(f"Translation failed for '{text[:30]}...' to '{target}': {e}")
        _translation_cache[cache_key] = None
        return None


def expand_query_for_bm25(query: str) -> List[str]:
    """
    Menghasilkan beberapa versi query untuk BM25:
    1. Query asli (original)
    2. Terjemahan ke Bahasa Indonesia (jika belum ID)
    3. Terjemahan ke Bahasa Inggris (jika belum EN)

    Dengan ini BM25 bisa mencocokkan keyword di KB bahasa apapun.
    """
    results = [query]  # selalu sertakan query asli

    for lang in SUPPORTED_LANGUAGES:
        translated = detect_and_translate(query, lang)
        if translated and translated not in results:
            results.append(translated)

    if len(results) > 1:
        logger.debug(f"BM25 query expansion: {results}")

    return results


def clear_translation_cache():
    """Bersihkan cache (berguna jika ada memory concern)."""
    global _translation_cache
    _translation_cache.clear()
    logger.info("Translation cache cleared")