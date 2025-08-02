import logging
import os

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
from dotenv import load_dotenv
from app import STORAGE_DIR, CHROMA_DB_PATH, CHROMA_DB_COLLECTION, init_settings


from llama_index.core.indices import (
    VectorStoreIndex,
)

from llama_index.core.readers import SimpleDirectoryReader

def load_custom_file_reader():
    custom_file_reader_cls = SimpleDirectoryReader.supported_suffix_fn()
    from llama_index.core.readers.base import BaseReader
    from typing import Type
    from llama_index.readers.file import  HTMLTagReader 
    custom_file_reader_cls: dict[str, Type[BaseReader]] = {
        ".htm": HTMLTagReader(tag='body'),
    }
    return custom_file_reader_cls

def generate_index():
    """
    Index the documents in the data directory.
    """
    from llama_index.core.readers import SimpleDirectoryReader

    load_dotenv()
    init_settings()

    logger.info("Creating new index")
    # load the documents and create the index
    reader = SimpleDirectoryReader(
        os.environ.get("DATA_DIR", "data"),
        recursive=True,
        file_extractor=load_custom_file_reader()
    )
    documents = reader.load_data()
    for document in documents:
        print(f'index document: {document.get_content()}')
    from app import is_chroma_index
    if is_chroma_index is None:
        get_index(documents)
    else:
        get_chroma_index(documents)

def get_index(documents):
    logger.info(f"load simple store")
    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True,
    )
    # store it for later
    index.storage_context.persist(STORAGE_DIR)
    logger.info(f"Finished creating new index. Stored in {STORAGE_DIR}")
    return index

def get_chroma_index(documents):
    logger.info(f"load chroma")
    import chromadb
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.core import StorageContext
    db = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    chroma_collection = db.get_or_create_collection(CHROMA_DB_COLLECTION)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(documents,
                                            storage_context=storage_context,
                                            show_progress=True)
    return index

generate_index()
