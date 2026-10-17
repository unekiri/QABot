"""ベクトル検索とキーワード検索(BM25)を組み合わせた根拠選択。

製造業の文書は品番・図番・工程コードを多く含むため、意味の近さだけでなく
文字列としての一致も検索に使う。キーワード索引はChromaDBの内容から
API内で組み立て、保存先をChromaDBの1か所に保つ。
"""
import hashlib
import math
import re
import threading
import unicodedata
from collections import Counter, defaultdict

CODE_PATTERN = re.compile(r'[a-z0-9]+(?:[-_./][a-z0-9]+)*')
CJK_PATTERN = re.compile(r'[぀-ヿ㐀-䶿一-鿿豈-﫿]+')
DATE_PATTERN = re.compile(r'(?:\d{4}[-/.])?\d{1,2}[-/.]\d{1,2}')
CODE_SEPARATORS = re.compile(r'[-_./]')


def normalize(text):
    """全角英数字・半角カナの揺れをなくし、大文字小文字を区別しない形にする。"""
    return unicodedata.normalize('NFKC', text or '').lower()


def tokenize(text):
    """英数字はまとまり(品番など)と区切り単位で、日本語は文字bigramで分割する。"""
    text = normalize(text)
    tokens = []
    for match in CODE_PATTERN.finditer(text):
        token = match.group()
        tokens.append(token)
        parts = [part for part in CODE_SEPARATORS.split(token) if part]
        if len(parts) > 1:
            tokens.extend(parts)
    for match in CJK_PATTERN.finditer(text):
        run = match.group()
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def extract_codes(text):
    """質問から品番・図番・製番らしい文字列を取り出す。

    数字を含み、6文字以上か英字と数字が混在する3文字以上のものを対象とする。
    日付(2026-10-17、10/17)は除外する。
    """
    codes = []
    for match in CODE_PATTERN.finditer(normalize(text)):
        token = match.group()
        if DATE_PATTERN.fullmatch(token):
            continue
        has_digit = any(char.isdigit() for char in token)
        has_alpha = any(char.isalpha() for char in token)
        if has_digit and (len(token) >= 6 or (has_alpha and len(token) >= 3)):
            codes.append(token)
    return list(dict.fromkeys(codes))


def contains_codes(text, codes):
    """全てのコードが前後を英数字に挟まれずに含まれるか(110601280 は 1106012800 に一致しない)。"""
    normalized = normalize(text)
    return all(re.search(rf'(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])', normalized)
               for code in codes)


class KeywordIndex:
    """チャンク単位のBM25索引。"""

    def __init__(self, ids, documents, metadatas, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.rows = {}
        self.postings = defaultdict(list)
        lengths = []
        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            if not document:
                continue
            frequencies = Counter(tokenize(document))
            position = len(lengths)
            lengths.append(sum(frequencies.values()))
            self.rows[chunk_id] = (document, metadata or {}, position)
            for term, frequency in frequencies.items():
                self.postings[term].append((chunk_id, frequency, position))
        self.lengths = lengths
        self.average_length = (sum(lengths) / len(lengths)) if lengths else 1
        total = len(lengths)
        self.idf = {term: math.log(1 + (total - len(items) + 0.5) / (len(items) + 0.5))
                    for term, items in self.postings.items()}

    def __len__(self):
        return len(self.rows)

    def search(self, query, limit):
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for chunk_id, frequency, position in self.postings[term]:
                length_ratio = self.lengths[position] / self.average_length
                denominator = frequency + self.k1 * (1 - self.b + self.b * length_ratio)
                scores[chunk_id] += idf * frequency * (self.k1 + 1) / denominator
        ranked = sorted(scores.items(), key=lambda item: (-item[1], self.rows[item[0]][2]))
        return [chunk_id for chunk_id, _ in ranked[:limit]]

    def get(self, chunk_id):
        row = self.rows.get(chunk_id)
        return (row[0], row[1]) if row else (None, None)


class KeywordIndexCache:
    """ChromaDBのチャンクIDが変わった時だけ索引を作り直す。

    チャンクIDには文書の改訂ハッシュが含まれるため、取り込みや改訂でIDの集合が変わる。
    """

    def __init__(self, page_size=1000):
        self.page_size = page_size
        self.fingerprint = None
        self.index = KeywordIndex([], [], [])
        self.lock = threading.Lock()

    def _fetch(self, collection, include):
        ids, documents, metadatas = [], [], []
        offset = 0
        while True:
            page = collection.get(include=include, limit=self.page_size, offset=offset)
            ids.extend(page['ids'])
            documents.extend(page.get('documents') or [])
            metadatas.extend(page.get('metadatas') or [])
            if len(page['ids']) < self.page_size:
                return ids, documents, metadatas
            offset += self.page_size

    def get(self, collection):
        ids, _, _ = self._fetch(collection, [])
        fingerprint = hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()
        with self.lock:
            if fingerprint == self.fingerprint:
                return self.index
            ids, documents, metadatas = self._fetch(collection, ['documents', 'metadatas'])
            self.index = KeywordIndex(ids, documents, metadatas)
            self.fingerprint = fingerprint
            return self.index


def rrf_fuse(rankings, k=60):
    """Reciprocal Rank Fusion: 各検索の順位だけを使って統合する(スコアの尺度差を無視できる)。"""
    scores = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda key: -scores[key])


def cosine(left, right):
    if right is None or len(left) != len(right):
        return None
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = (math.sqrt(sum(a * a for a in left))
                   * math.sqrt(sum(b * b for b in right)))
    if not denominator:
        return None
    score = numerator / denominator
    return score if math.isfinite(score) else None


def select_hybrid_evidence(question, question_embedding, vector_results, keyword_index,
                           fetch_embeddings, minimum_relevance, top_k=3,
                           candidates=20, code_filter=True):
    """ベクトル検索とキーワード検索の結果をRRFで統合し、根拠として使えるチャンクを選ぶ。

    採用条件:
    - 質問に品番等のコードがある場合(code_filter有効時)、そのコードを含むチャンクだけを採用する。
      コードを含むチャンクは意味の類似度が低くても採用する。
    - コードがない場合は、従来どおり類似度がminimum_relevance以上のチャンクだけを採用する。
    """
    if not 0 <= minimum_relevance <= 1:
        raise ValueError('MIN_RELEVANCE must be between 0 and 1')
    vector_rows = {}
    vector_ranking = []
    if vector_results and vector_results.get('ids'):
        for chunk_id, document, metadata, vector in zip(
            vector_results['ids'][0], vector_results['documents'][0],
            vector_results['metadatas'][0], vector_results['embeddings'][0],
        ):
            vector_rows[chunk_id] = (document, metadata or {}, vector)
            vector_ranking.append(chunk_id)
    keyword_ranking = keyword_index.search(question, candidates) if keyword_index is not None else []
    codes = extract_codes(question) if code_filter else []

    fused = rrf_fuse([vector_ranking, keyword_ranking])
    missing = [chunk_id for chunk_id in fused if chunk_id not in vector_rows]
    fetched = fetch_embeddings(missing) if missing else {}

    evidence = []
    for chunk_id in fused:
        if chunk_id in vector_rows:
            document, metadata, vector = vector_rows[chunk_id]
        else:
            document, metadata = keyword_index.get(chunk_id)
            vector = fetched.get(chunk_id)
        if not document:
            continue
        if codes:
            if not contains_codes(document, codes):
                continue
        else:
            score = cosine(question_embedding, vector)
            if score is None or score < minimum_relevance:
                continue
        metadata = metadata or {}
        evidence.append({
            'id': chunk_id,
            'source': metadata.get('source') or '出典不明',
            'excerpt': document,
            'page': metadata.get('page'),
        })
        if len(evidence) >= top_k:
            break
    return evidence
