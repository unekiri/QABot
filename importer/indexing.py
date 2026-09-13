import hashlib
import json
import shutil
import uuid
from pathlib import Path


def index_document(collection, embed_documents, chunks, source_path, doc_dir, logs_dir):
    source_path = Path(source_path).resolve()
    relative_path = source_path.relative_to(Path(doc_dir).resolve()).as_posix()
    document_id = hashlib.sha256(relative_path.encode()).hexdigest()
    texts = [chunk.page_content for chunk in chunks if chunk.page_content.strip()]
    if not texts:
        raise ValueError(f'No text extracted: {relative_path}')
    chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
    revision = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()
    ids = [f'{document_id}:{revision}:{i}' for i in range(len(texts))]
    metadata = []
    for i, chunk in enumerate(chunks):
        item = {'source': relative_path, 'document_id': document_id, 'chunk_index': i}
        if chunk.metadata.get('page_number') is not None:
            item['page'] = str(chunk.metadata['page_number'])
        metadata.append(item)

    # Include legacy records indexed with an absolute source path.
    source_aliases = {relative_path, str(source_path), source_path.as_posix()}
    source_aliases.update(str(chunk.metadata['source']) for chunk in chunks if chunk.metadata.get('source'))
    previous = collection.get(where={'$or': [
        {'document_id': document_id},
        *[{'source': source} for source in sorted(source_aliases)],
    ]}, include=['metadatas'])
    vectors = embed_documents(texts)
    for start in range(0, len(ids), 100):
        batch = slice(start, start + 100)
        collection.upsert(ids=ids[batch], documents=texts[batch],
                          embeddings=vectors[batch], metadatas=metadata[batch])
    stored = collection.get(ids=ids, include=['documents', 'metadatas'])
    actual = {key: (text, meta) for key, text, meta in zip(
        stored['ids'], stored['documents'], stored['metadatas'])}
    expected = {key: (text, meta) for key, text, meta in zip(ids, texts, metadata)}
    if actual != expected:
        raise RuntimeError(f'Index verification failed: {relative_path}')

    obsolete = sorted(set(previous['ids']) - set(ids))
    if obsolete:
        collection.delete(ids=obsolete)
        if collection.get(ids=obsolete, include=['metadatas'])['ids']:
            raise RuntimeError(f'Old chunks remain: {relative_path}')

    # A unique directory preserves earlier originals and equal basenames.
    destination = Path(logs_dir) / uuid.uuid4().hex / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(destination))
    return len(ids)
