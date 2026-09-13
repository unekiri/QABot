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
from rag import select_evidence, create_prompt, parse_answer, ANSWER_SCHEMA, NO_EVIDENCE
from indexing import index_document


class MemoryCollection:
    def __init__(self):
        self.rows = {}
        self.drop_write = False
        self.fail_delete = False

    def get(self, ids=None, where=None, include=None):
        selected = list(self.rows) if ids is None else [key for key in ids if key in self.rows]
        if where:
            selected = [key for key in selected if any(
                all(self.rows[key][1].get(field) == value for field, value in clause.items())
                for clause in where['$or'])]
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


class RagTests(unittest.TestCase):
    def results(self, vectors, documents=None):
        return {'ids': [[str(i) for i in range(len(vectors))]],
                'documents': [documents or ['返却期限は貸出日から7日です。'] * len(vectors)],
                'metadatas': [[{'source': '貸出規程.txt', 'page': '2'}] * len(vectors)],
                'embeddings': [vectors]}

    def test_relevant_evidence_includes_source_and_excerpt(self):
        evidence = select_evidence(self.results([[10, 0], [0, 10]]), [2, 0], .8)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]['source'], '貸出規程.txt')
        self.assertEqual(evidence[0]['page'], '2')
        self.assertIn('7日', evidence[0]['excerpt'])

    def test_unrelated_and_invalid_vectors_are_rejected(self):
        self.assertEqual(select_evidence(self.results([[0, 1], [0, 0], [float('nan'), 1]]), [1, 0], .8), [])

    def test_empty_collection(self):
        self.assertEqual(select_evidence(self.results([]), [1, 0], .8), [])

    def test_prompt_requires_abstention_and_source(self):
        evidence = select_evidence(self.results([[1, 0]]), [1, 0], .8)
        prompt = create_prompt('返却期限は？', evidence)
        self.assertIn('"answer":null', prompt)
        self.assertIn('貸出規程.txt', prompt)
        self.assertIn('7日', prompt)

    def test_api_syntax(self):
        ast.parse((ROOT / 'api/main.py').read_text(encoding='utf-8'))

    def call_api(self, results, answer='返却期限は7日です。', count=1):
        tree = ast.parse((ROOT / 'api/main.py').read_text(encoding='utf-8'))
        route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'ask_question')
        route.decorator_list = []
        collection = Mock()
        collection.count.return_value = count
        collection.query.return_value = results
        embeddings = Mock()
        embeddings.encode.return_value.tolist.return_value = [1, 0]
        llm = Mock()
        llm.generate.return_value = {'response': json.dumps({
            'quote': None if answer == NO_EVIDENCE else '返却期限は貸出日から7日です。',
            'answer': None if answer == NO_EVIDENCE else answer,
        })}
        namespace = dict(QuestionRequest=SimpleNamespace, AnswerResponse=SimpleNamespace,
                         collection=collection, embeddings=embeddings, ollama_client=llm,
                         LLM_MODEL='test', select_evidence=select_evidence, create_prompt=create_prompt,
                         NO_EVIDENCE=NO_EVIDENCE, parse_answer=parse_answer, ANSWER_SCHEMA=ANSWER_SCHEMA,
                         os=SimpleNamespace(getenv=lambda key, default: default),
                         HTTPException=RuntimeError)
        exec(compile(ast.Module(body=[route], type_ignores=[]), 'api/main.py', 'exec'), namespace)
        response = asyncio.run(namespace['ask_question'](SimpleNamespace(question='返却期限は？')))
        return response, llm

    def test_api_skips_llm_for_empty_collection(self):
        response, llm = self.call_api(self.results([]), count=0)
        self.assertTrue(response.abstained)
        llm.generate.assert_not_called()

    def test_api_skips_llm_for_unrelated_results(self):
        response, llm = self.call_api(self.results([[0, 1]]))
        self.assertTrue(response.abstained)
        self.assertEqual(response.evidence, [])
        llm.generate.assert_not_called()

    def test_api_returns_evidence_with_answer(self):
        response, llm = self.call_api(self.results([[1, 0]]))
        self.assertFalse(response.abstained)
        self.assertEqual(response.sources, ['貸出規程.txt'])
        self.assertIn('7日', response.answer)
        llm.generate.assert_called_once()

    def test_api_recognizes_llm_abstention(self):
        response, _ = self.call_api(self.results([[1, 0]]), answer=NO_EVIDENCE)
        self.assertTrue(response.abstained)

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
