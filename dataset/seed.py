import json
import re
from pathlib import Path

from pymongo import MongoClient, ASCENDING

# --- Настройки ---
DATASET_DIR = Path(__file__).resolve().parent               # папка с .jsonl файлами
MONGO_URI = "mongodb://localhost:27017"       
DB_NAME = "stylometry"                        # имя базы данных

CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
LATIN_RE = re.compile(r"[A-Za-z]")

def is_russian(text: str, min_chars: int = 10) -> bool:
    cyr = len(CYRILLIC_RE.findall(text))
    lat = len(LATIN_RE.findall(text))
    return cyr > min_chars and cyr > lat

def build_nested_doc(records: list[dict]) -> dict:
    """Превращает плоские записи {author, source, text, word_count}
    во вложенный документ: author -> works[] -> chunks[]."
    """
    author = records[0]["author"]
    works = {}                                 # source -> список чанков, сохраняет порядок

    for rec in records:
        if is_russian(rec.get('text', '')):
            continue
        works.setdefault(rec["source"], []).append(
            {"text": rec["text"], "word_count": rec.get("word_count")}
        )

    return {
        "author": author,
        "works": [
            {"source": source, "chunks": chunks} for source, chunks in works.items()
        ],
    }

def load_dataset(dataset_dir: Path):
    """Читает каждый .jsonl-файл и отдаёт (collection_name, document)."""
    for path in sorted(dataset_dir.glob("*.jsonl")):
        records = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        if not records:
            continue

        # Имя коллекции = имя файла (lewis.jsonl -> lewis)
        collection_name = path.stem
        yield collection_name, build_nested_doc(records)

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    styles_path = DATASET_DIR / 'styles.json'
    with styles_path.open(encoding="utf-8") as f:
        styles = json.load(f) 
    
    for collection_name, doc in load_dataset(DATASET_DIR):
        collection = db[collection_name]

        # Индексы для стилометрических запросов
        collection.create_index([("author", ASCENDING)])
        collection.create_index([("works.source", ASCENDING)])

        # Один документ на автора (файл) — заменяем при повторном запуске
        # Добавить стиль автора из styles
        author_style = styles.get(doc['author'], {}).get('style')
        if author_style is not None:
            doc['style'] = author_style
        collection.replace_one({"author": doc["author"]}, doc, upsert=True)

        n_chunks = sum(len(w["chunks"]) for w in doc["works"])
        print(f"{collection_name}: {len(doc['works'])} книг, {n_chunks} чанков -> inserted/replaced")

    client.close()
    print("Готово.")

if __name__ == "__main__":
    main()