import re
import math


def sentence_tokenizer(text):
    """
    Improved sentence tokenizer that handles common abbreviations better.
    """
    # Handle common abbreviations that shouldn't end sentences
    text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|etc|i\.e|e\.g)\.', r'\1<PRD>', text)

    # Split on sentence endings
    sentences = re.split(r'[.!?]+', text)

    # Restore abbreviations
    sentences = [s.replace('<PRD>', '.').strip() for s in sentences]

    # Filter out very short sentences but keep meaningful ones
    return [s for s in sentences if len(s.strip()) >= 15]  # Reduced from 20 to 15 for better coverage


def word_tokenizer(sentence):
    return re.findall(r'\b\w+\b', sentence.lower())


def similarity(sent1, sent2):
    words1 = set(word_tokenizer(sent1))
    words2 = set(word_tokenizer(sent2))
    if not words1 or not words2:
        return 0
    return len(words1 & words2) / (math.sqrt(len(words1)) * math.sqrt(len(words2)))


def position_weight(index, total_sentences):
    """
    Give slightly higher weight to sentences at beginning and end of document.
    """
    if total_sentences <= 2:
        return 1.0
    # Normalize position to 0-1 range
    normalized_pos = index / (total_sentences - 1)
    # U-shaped weighting: higher at beginning (0) and end (1), lower in middle
    if normalized_pos <= 0.3:
        return 1.2  # Beginning boost
    elif normalized_pos >= 0.7:
        return 1.1  # End boost
    else:
        return 1.0  # Normal weight


def length_normalization_score(sentence, avg_length):
    """
    Normalize sentence score by length to avoid bias toward very long/short sentences.
    """
    length = len(sentence.split())
    if length == 0:
        return 0
    # Optimal length is around average - penalize extremes
    length_ratio = length / max(avg_length, 1)
    if length_ratio < 0.5 or length_ratio > 2.0:
        return 0.8  # Slight penalty for extreme lengths
    return 1.0


MAX_SUMMARY_CHARS = 100_000


def textrank_summary(text, num_sentences=3):
    """Summarize bounded input with deterministic sentence selection."""
    try:
        num_sentences = int(num_sentences)
    except (TypeError, ValueError) as exc:
        raise ValueError('num_sentences must be an integer') from exc
    if num_sentences < 1:
        raise ValueError('num_sentences must be positive')
    if not text:
        return ''
    if len(text) > MAX_SUMMARY_CHARS:
        raise ValueError(f'text exceeds the {MAX_SUMMARY_CHARS}-character limit')
    sentences = sentence_tokenizer(text)
    if len(sentences) <= num_sentences:
        return ' '.join(sentences)

    n = len(sentences)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                sim[i][j] = similarity(sentences[i], sentences[j])

    # Precompute each sentence's total outgoing similarity ("out-degree").
    out_degree = [sum(sim[j]) for j in range(n)]

    # Calculate average sentence length for normalization
    lengths = [len(s.split()) for s in sentences if s.strip()]
    avg_length = sum(lengths) / max(len(lengths), 1) if lengths else 1

    scores = [1.0] * n
    damping = 0.85

    for _ in range(30):  # a few more iterations, with early exit below
        new = [0.0] * n
        for i in range(n):
            total = 0.0
            for j in range(n):
                if i == j or out_degree[j] == 0:
                    continue
                # Apply position weighting and length normalization
                pos_weight = position_weight(j, n)
                length_norm = length_normalization_score(sentences[j], avg_length)
                weighted_sim = sim[j][i] * pos_weight * length_norm
                total += (weighted_sim / out_degree[j]) * scores[j]
            new[i] = (1 - damping) + damping * total

        # Early stop once scores settle
        if max(abs(new[i] - scores[i]) for i in range(n)) < 1e-4:
            scores = new
            break
        scores = new

    ranked = sorted(((scores[i], i) for i in range(n)), reverse=True)
    top_indices = sorted(idx for _, idx in ranked[:num_sentences])
    return ' '.join(sentences[i] for i in top_indices)