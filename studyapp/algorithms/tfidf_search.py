import re
import math
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

# Search must work in offline deployments.  The fallback keeps imports
# deterministic when the optional NLTK corpus is not installed.
_FALLBACK_STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
    'the', 'this', 'to', 'was', 'were', 'will', 'with', 'you',
}
_stemmer = PorterStemmer()
try:
    _stop_words = set(stopwords.words('english'))
except LookupError:
    _stop_words = _FALLBACK_STOP_WORDS


def _tokenize(text):
    """Enhanced tokenizer with stemming and stopword removal."""
    words = re.findall(r'\b\w+\b', text.lower())
    # Remove stopwords and apply stemming
    meaningful_words = [_stemmer.stem(word) for word in words if word not in _stop_words]
    return meaningful_words


def _basic_tokenize(text):
    """Basic tokenizer for fallback (no stemming/stopword removal)."""
    return re.findall(r'\b\w+\b', text.lower())


def compute_tf(term, doc):
    words = _tokenize(doc)
    if not words:
        return 0
    # Stem the term for matching
    stemmed_term = _stemmer.stem(term.lower())
    return words.count(stemmed_term) / len(words)


def compute_idf(term, docs):
    """Counts documents that actually contain `term` as a whole word,
    not as a substring — so 'cat' no longer matches 'category'."""
    if not docs:
        return 0
    # Stem the term for matching
    stemmed_term = _stemmer.stem(term.lower())
    count = sum(1 for d in docs if stemmed_term in _tokenize(d))
    if count == 0:
        return 0
    # +1 smoothing avoids a zero-division edge case and keeps the score
    # finite even when a term appears in every document.
    return math.log((1 + len(docs)) / (1 + count)) + 1


def tfidf_search(query, docs, doc_ids, top_k=5):
    """Rank matching documents, rejecting misaligned or invalid inputs."""
    if len(docs) != len(doc_ids):
        raise ValueError('docs and doc_ids must have the same length')
    try:
        top_k = int(top_k)
    except (TypeError, ValueError) as exc:
        raise ValueError('top_k must be an integer') from exc
    if top_k < 0:
        raise ValueError('top_k must not be negative')
    if not docs or not doc_ids or top_k == 0:
        return []

    query_terms = set(_tokenize(query or ''))
    if not query_terms:
        return []

    # Compute each term's IDF once, up front, instead of recomputing it
    # from scratch inside the per-document loop below.
    idf_cache = {term: compute_idf(term, docs) for term in query_terms}

    results = []
    for idx, doc in enumerate(docs):
        score = sum(compute_tf(term, doc) * idf_cache[term] for term in query_terms)
        results.append((doc_ids[idx], score))

    results.sort(key=lambda x: x[1], reverse=True)
    return [r for r in results if r[1] > 0][:top_k]