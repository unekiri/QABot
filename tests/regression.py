import ast
import asyncio
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'importer'))
from rag import create_prompt, parse_answer, ANSWER_SCHEMA, NO_EVIDENCE
from search import (KeywordIndex, KeywordIndexCache, contains_codes, extract_codes,
                    rrf_fuse, select_hybrid_evidence, tokenize)
from indexing import index_document


class MemoryCollection:
    def __init__(self):
        self.rows = {}
        self.drop_write = False
        self.fail_delete = False

    def get(self, ids=None, where=None, include=None, limit=None, offset=0):
        selected = list(self.rows) if ids is None else [key for key in ids if key in self.rows]
        if where:
            selected = [key for key in selected if any(
                all(self.rows[key][1].get(field) == value for field, value in clause.items())
                for clause in where['$or'])]
        selected = selected[offset:None if limit is None else offset + limit]
        return {'ids': selected,
                'documents': [self.rows[key][0] for key in selected],
                'metadatas': [self.rows[key][1] for key in selected]}

    def upsert(self, ids, documents, embeddings, metadatas):
        if self.drop_write:
            return
        for key, text, metadata in zip(ids, documents, metadatas):
            self.rows[key] = (text, metadata)

    def delete(self, ids):
        if self.fail_delete:
            raise RuntimeError('delete unavailable')
        for key in ids:
            self.rows.pop(key, None)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.docs = Path(self.temp.name) / 'documents'
        self.logs = Path(self.temp.name) / 'logs'
        self.docs.mkdir()
        self.collection = MemoryCollection()

    def run_import(self, name, texts):
        source = self.docs / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('\n'.join(texts), encoding='utf-8')
        chunks = [SimpleNamespace(page_content=text, metadata={'source': str(source)}) for text in texts]
        index_document(self.collection, lambda values: [[1, 0] for _ in values],
                       chunks, source, self.docs, self.logs)
        return source

    def test_different_documents_do_not_collide(self):
        self.run_import('a/manual.txt', ['A'])
        self.run_import('b/manual.txt', ['B'])
        self.assertEqual(len(self.collection.rows), 2)
        self.assertEqual(len(list(self.logs.rglob('manual.txt'))), 2)

    def test_repeat_import_is_idempotent_and_preserves_archives(self):
        self.run_import('manual.txt', ['A', 'B'])
        original_ids = set(self.collection.rows)
        self.run_import('manual.txt', ['A', 'B'])
        self.assertEqual(set(self.collection.rows), original_ids)
        self.assertEqual(len(list(self.logs.rglob('manual.txt'))), 2)

    def test_shorter_revision_removes_old_chunks_only(self):
        self.run_import('other.txt', ['OTHER'])
        self.run_import('manual.txt', ['A', 'B', 'C'])
        self.run_import('manual.txt', ['NEW'])
        self.assertEqual({row[0] for row in self.collection.rows.values()}, {'NEW', 'OTHER'})

    def test_failed_verification_keeps_original_and_old_index(self):
        self.run_import('manual.txt', ['OLD'])
        previous = copy.deepcopy(self.collection.rows)
        self.collection.drop_write = True
        with self.assertRaises(RuntimeError):
            self.run_import('manual.txt', ['NEW'])
        self.assertTrue((self.docs / 'manual.txt').exists())
        self.assertEqual(self.collection.rows, previous)

    def test_cleanup_failure_can_be_retried(self):
        self.run_import('manual.txt', ['OLD'])
        self.collection.fail_delete = True
        with self.assertRaises(RuntimeError):
            self.run_import('manual.txt', ['NEW'])
        self.assertTrue((self.docs / 'manual.txt').exists())
        self.collection.fail_delete = False
        self.run_import('manual.txt', ['NEW'])
        self.assertEqual([row[0] for row in self.collection.rows.values()], ['NEW'])

    def test_legacy_source_records_replaced(self):
        self.collection.rows['doc0'] = ('OLD', {'source': str(self.docs / 'manual.txt')})
        self.run_import('manual.txt', ['NEW'])
        self.assertNotIn('doc0', self.collection.rows)

    def test_empty_document_is_not_archived(self):
        with self.assertRaises(ValueError):
            self.run_import('manual.txt', ['   '])
        self.assertTrue((self.docs / 'manual.txt').exists())


def vector_results(rows):
    """rows: [(id, document, metadata, embedding)]"""
    return {'ids': [[row[0] for row in rows]],
            'documents': [[row[1] for row in rows]],
            'metadatas': [[row[2] for row in rows]],
            'embeddings': [[row[3] for row in rows]]}


LOAN = '返却期限は貸出日から7日です。'
LOAN_META = {'source': '貸出規程.txt', 'page': '2'}


class SearchTests(unittest.TestCase):
    def select(self, question, rows, index_rows=None, fetched=None, **options):
        index_rows = rows if index_rows is None else index_rows
        index = KeywordIndex([r[0] for r in index_rows], [r[1] for r in index_rows],
                             [r[2] for r in index_rows])
        fetch = Mock(return_value=fetched or {})
        evidence = select_hybrid_evidence(question, [1, 0], vector_results(rows), index,
                                          fetch, options.pop('minimum_relevance', .8), **options)
        return evidence, fetch

    def test_tokenize_keeps_codes_and_normalizes_width(self):
        tokens = tokenize('品番Ａ－１２３４－０５の検査')
        self.assertIn('a-1234-05', tokens)
        self.assertIn('1234', tokens)
        self.assertIn('品番', tokens)
        self.assertIn('検査', tokens)

    def test_extract_codes_ignores_dates_and_small_numbers(self):
        self.assertEqual(extract_codes('110601280の検査基準は？'), ['110601280'])
        self.assertEqual(extract_codes('製番M7418とF35の工程は？'), ['m7418', 'f35'])
        self.assertEqual(extract_codes('2026-10-17に7日間、2026年の計画は？'), [])

    def test_contains_codes_respects_boundaries(self):
        self.assertTrue(contains_codes('品番110601280の検査基準', ['110601280']))
        self.assertFalse(contains_codes('品番1106012800の検査基準', ['110601280']))
        self.assertTrue(contains_codes('図番 Ａ－１２３４－０５ 改訂B', ['a-1234-05']))

    def test_bm25_ranks_exact_code_first(self):
        index = KeywordIndex(['a', 'b', 'c'],
                             ['品番110601280の検査基準は外径測定。', '品番110601281の検査基準は硬度。', '貸出規程'],
                             [{}, {}, {}])
        self.assertEqual(index.search('110601280の検査基準', 3)[0], 'a')
        self.assertEqual(index.search('関係のない質問zzz', 3), [])

    def test_rrf_rewards_agreement(self):
        self.assertEqual(rrf_fuse([['a', 'b'], ['b', 'c']])[0], 'b')

    def test_relevant_evidence_includes_source_and_excerpt(self):
        evidence, _ = self.select('返却期限は？', [('0', LOAN, LOAN_META, [10, 0]), ('1', LOAN, LOAN_META, [0, 10])])
        self.assertEqual([item['id'] for item in evidence], ['0'])
        self.assertEqual(evidence[0]['source'], '貸出規程.txt')
        self.assertEqual(evidence[0]['page'], '2')
        self.assertIn('7日', evidence[0]['excerpt'])

    def test_unrelated_and_invalid_vectors_are_rejected(self):
        rows = [('0', LOAN, LOAN_META, [0, 1]), ('1', LOAN, LOAN_META, [0, 0]),
                ('2', LOAN, LOAN_META, [float('nan'), 1])]
        self.assertEqual(self.select('返却期限は？', rows)[0], [])

    def test_empty_collection(self):
        self.assertEqual(self.select('返却期限は？', [])[0], [])

    def test_invalid_threshold_is_rejected(self):
        with self.assertRaises(ValueError):
            self.select('返却期限は？', [], minimum_relevance=1.5)

    def test_code_question_finds_keyword_only_chunk(self):
        # 意味検索では別品番しか上位に来ないが、キーワード検索で正しい品番を拾う
        target = ('t', '品番110601280の検査基準は外径測定です。', {'source': '検査基準.xlsx'}, [0, 1])
        other = ('o', '品番110601281の検査基準は硬度測定です。', {'source': '検査基準.xlsx'}, [1, 0])
        evidence, fetch = self.select('110601280の検査基準は？', [other], index_rows=[other, target],
                                      fetched={'t': [0, 1]})
        self.assertEqual([item['id'] for item in evidence], ['t'])
        fetch.assert_called_once_with(['t'])

    def test_code_filter_rejects_semantically_similar_wrong_code(self):
        other = ('o', '品番110601281の検査基準は硬度測定です。', {'source': '検査基準.xlsx'}, [1, 0])
        self.assertEqual(self.select('110601280の検査基準は？', [other])[0], [])

    def test_code_filter_can_be_disabled(self):
        other = ('o', '品番110601281の検査基準は硬度測定です。', {'source': '検査基準.xlsx'}, [1, 0])
        evidence, _ = self.select('110601280の検査基準は？', [other], code_filter=False)
        self.assertEqual([item['id'] for item in evidence], ['o'])

    def test_keyword_hit_without_code_still_needs_relevance(self):
        unrelated = ('u', '返却期限の話ではない文書。返却期限', LOAN_META, [0, 1])
        evidence, _ = self.select('返却期限は？', [], index_rows=[unrelated], fetched={'u': [0, 1]})
        self.assertEqual(evidence, [])

    def test_top_k_limits_evidence(self):
        rows = [(str(i), LOAN, LOAN_META, [1, 0]) for i in range(5)]
        self.assertEqual(len(self.select('返却期限は？', rows, top_k=2)[0]), 2)


class KeywordCacheTests(unittest.TestCase):
    def test_rebuilds_only_when_chunk_ids_change(self):
        collection = MemoryCollection()
        collection.rows['a'] = ('品番110601280', {'source': 'a.txt'})
        cache = KeywordIndexCache(page_size=1)
        first = cache.get(collection)
        self.assertIs(cache.get(collection), first)
        collection.rows['b'] = ('品番110601281', {'source': 'b.txt'})
        second = cache.get(collection)
        self.assertIsNot(second, first)
        self.assertEqual(len(second), 2)
        self.assertEqual(second.search('110601281', 1), ['b'])


class RagTests(unittest.TestCase):
    def test_prompt_requires_abstention_and_source(self):
        evidence = [{'id': '0', 'source': '貸出規程.txt', 'excerpt': LOAN, 'page': '2'}]
        prompt = create_prompt('返却期限は？', evidence)
        self.assertIn('"answer":null', prompt)
        self.assertIn('貸出規程.txt', prompt)
        self.assertIn('7日', prompt)

    def test_api_syntax(self):
        ast.parse((ROOT / 'api/main.py').read_text(encoding='utf-8'))

    def call_api(self, rows, answer='返却期限は7日です。', count=1, question='返却期限は？'):
        tree = ast.parse((ROOT / 'api/main.py').read_text(encoding='utf-8'))
        route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'ask_question')
        route.decorator_list = []
        collection = Mock()
        collection.count.return_value = count
        collection.query.return_value = vector_results(rows)
        index = KeywordIndex([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])
        keyword_indexes = Mock()
        keyword_indexes.get.return_value = index
        embeddings = Mock()
        embeddings.encode.return_value.tolist.return_value = [1, 0]
        llm = Mock()
        llm.generate.return_value = {'response': json.dumps({
            'quote': None if answer == NO_EVIDENCE else LOAN,
            'answer': None if answer == NO_EVIDENCE else answer,
        })}
        namespace = dict(QuestionRequest=SimpleNamespace, AnswerResponse=SimpleNamespace,
                         collection=collection, embeddings=embeddings, ollama_client=llm,
                         LLM_MODEL='test', select_hybrid_evidence=select_hybrid_evidence,
                         keyword_indexes=keyword_indexes, fetch_embeddings=Mock(return_value={}),
                         create_prompt=create_prompt,
                         NO_EVIDENCE=NO_EVIDENCE, parse_answer=parse_answer, ANSWER_SCHEMA=ANSWER_SCHEMA,
                         os=SimpleNamespace(getenv=lambda key, default: default),
                         HTTPException=RuntimeError)
        exec(compile(ast.Module(body=[route], type_ignores=[]), 'api/main.py', 'exec'), namespace)
        response = asyncio.run(namespace['ask_question'](SimpleNamespace(question=question)))
        return response, llm

    def test_api_skips_llm_for_empty_collection(self):
        response, llm = self.call_api([], count=0)
        self.assertTrue(response.abstained)
        llm.generate.assert_not_called()

    def test_api_skips_llm_for_unrelated_results(self):
        response, llm = self.call_api([('0', LOAN, LOAN_META, [0, 1])])
        self.assertTrue(response.abstained)
        self.assertEqual(response.evidence, [])
        llm.generate.assert_not_called()

    def test_api_returns_evidence_with_answer(self):
        response, llm = self.call_api([('0', LOAN, LOAN_META, [1, 0])])
        self.assertFalse(response.abstained)
        self.assertEqual(response.sources, ['貸出規程.txt'])
        self.assertIn('7日', response.answer)
        llm.generate.assert_called_once()

    def test_api_recognizes_llm_abstention(self):
        response, _ = self.call_api([('0', LOAN, LOAN_META, [1, 0])], answer=NO_EVIDENCE)
        self.assertTrue(response.abstained)

    def test_api_abstains_for_unknown_part_number(self):
        response, llm = self.call_api([('0', LOAN, LOAN_META, [1, 0])], question='品番999999999の返却期限は？')
        self.assertTrue(response.abstained)
        llm.generate.assert_not_called()

    def test_null_answer_becomes_standard_abstention(self):
        answer, abstained = parse_answer('{"quote":null,"answer":null}', [])
        self.assertTrue(abstained)
        self.assertEqual(answer, NO_EVIDENCE)

    def test_malformed_generation_is_not_presented_as_an_answer(self):
        for raw in ['invalid', '[]', '{}', '{"answer":42}', '{"answer":""}', '{"answer":"foo","abstained":true}']:
            self.assertEqual(parse_answer(raw, []), (NO_EVIDENCE, True))

    def test_nonempty_answer_is_accepted(self):
        self.assertEqual(parse_answer('{"quote":"期限は14日","answer":"14日です。"}',
                                      [{'excerpt': '期限は14日です。'}]), ('14日です。', False))

    def test_unsupported_quote_is_rejected(self):
        self.assertEqual(parse_answer('{"quote":"延滞料金は100円","answer":"100円です。"}',
                                      [{'excerpt': '期限は14日です。'}]), (NO_EVIDENCE, True))

    def test_no_quote_is_abstention_even_with_explanation(self):
        self.assertEqual(parse_answer('{"quote":null,"answer":"資料には記載されていません。"}',
                                      [{'excerpt': '期限は14日です。'}]), (NO_EVIDENCE, True))

    def test_explained_abstention_with_irrelevant_quote(self):
        evidence = [{'excerpt': '期限は14日です。'}]
        for answer in ['資料からは十分な根拠を確認できないため、回答を保留します。',
                       '延滞料金は資料には記載されていません。',
                       '資料に該当する情報がありません。']:
            raw = json.dumps({'quote': '期限は14日です。', 'answer': answer})
            self.assertEqual(parse_answer(raw, evidence), (NO_EVIDENCE, True))

    def test_negative_fact_is_still_an_answer(self):
        raw = json.dumps({'quote': '延滞料金は発生しません。', 'answer': '延滞料金は発生しません。'})
        self.assertEqual(parse_answer(raw, [{'excerpt': '延滞料金は発生しません。'}]),
                         ('延滞料金は発生しません。', False))


if __name__ == '__main__':
    unittest.main()
