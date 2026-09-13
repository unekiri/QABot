import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/app')
import docsImporter
import chromadb

client = chromadb.HttpClient(host='chroma', port=8000)
collection = client.get_or_create_collection('integration_docs')
assert collection.count() == 0, 'Use a fresh isolated collection'

with tempfile.TemporaryDirectory() as directory:
    docsImporter.DOC_DIR = Path(directory)
    source = Path(directory) / 'loan-policy.txt'
    original = '機材貸出規程。社内の貸出用ノートパソコンの返却期限は貸出日から7日です。返却先は総務部です。'
    source.write_text(original, encoding='utf-8')
    docsImporter.main()
    assert not source.exists()
    initial = collection.get(include=['documents', 'metadatas'])
    assert len(initial['ids']) > 0
    print('PASS initial import and archive', flush=True)

    source.write_text(original, encoding='utf-8')
    docsImporter.main()
    assert set(collection.get()['ids']) == set(initial['ids'])
    print('PASS idempotent re-import', flush=True)

    source.write_text('機材貸出規程。社内の貸出用ノートパソコンの返却期限は貸出日から14日です。返却先は総務部です。', encoding='utf-8')
    docsImporter.main()
    updated = collection.get(include=['documents', 'metadatas'])
    assert not set(initial['ids']) & set(updated['ids'])
    assert all('7日' not in text for text in updated['documents'])
    print('PASS revision replaces old chunks', flush=True)

    source = Path(directory) / 'parking-policy.txt'
    source.write_text('駐車場利用規程。社員用駐車場の利用申請は人事部に提出してください。来客用駐車場は正面玄関の横です。', encoding='utf-8')
    docsImporter.main()
    assert set(updated['ids']).issubset(set(collection.get()['ids']))
    assert collection.count() > len(updated['ids'])
    print('PASS additional document preserves previous document', flush=True)
print('PASS full importer integration', flush=True)
