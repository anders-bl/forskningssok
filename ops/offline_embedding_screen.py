"""Run a preregistered, local-only embedding screen against a frozen corpus slice.

The 2026-11-05 R2402 decision authorizes an offline screen, not a production
index migration. Keeping the database read-only and refusing model-side
truncation preserves that distinction and makes the measured input lengths
auditable.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import statistics
import time
import tomllib
import urllib.error
import urllib.request
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import sqlite_vec


ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "data" / "nomic_offline_screen_prereg_2026-11-05.json"
RESULT_PATH = ROOT / "data" / "nomic_offline_screen_results_2026-11-05.json"
DATABASE_PATH = Path("/Users/anders/prosjekter/bøker/boker.db")
MODEL = "nomic-embed-text:latest"
MODEL_BLOB = Path.home() / ".ollama/models/blobs/sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6"
EMBED_URL = "http://127.0.0.1:11434/api/embed"
VECTOR_DIMENSIONS = 768
CONTEXT_TOKENS = 2048
TOP_K = 5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def api_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"local embedding API returned HTTP {error.code}: {detail}") from error


def load_queries(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in prereg["query_sources"]:
        path = ROOT / source["path"]
        if sha256_file(path) != source["sha256"]:
            raise RuntimeError(f"query source changed after preregistration: {source['path']}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload[source["items_key"]]
        if len(items) != source["record_count"]:
            raise RuntimeError(f"query source row count changed: {source['path']}")
        for index, item in enumerate(items, start=1):
            query = item.get("sporring") or item.get("sporsmal")
            if not isinstance(query, str) or not query.strip():
                raise RuntimeError(f"empty query in {source['path']} row {index}")
            group = item.get("gruppe") or source.get("fixed_group") or item.get("tema") or "unspecified"
            rows.append({
                "query_id": f"{source['source_id']}-{index:03d}",
                "source_id": source["source_id"],
                "source_index": index,
                "group": group,
                "text": query,
                "normalized": " ".join(query.casefold().split()),
                "expected_title": item.get("forventet_dokument"),
            })
    if len(rows) != prereg["query_record_count"]:
        raise RuntimeError("query record count does not match preregistration")
    if len({row["normalized"] for row in rows}) != prereg["unique_query_count"]:
        raise RuntimeError("query uniqueness does not match preregistration")
    return rows


def load_corpus(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    if sha256_file(DATABASE_PATH) != prereg["corpus"]["sha256"]:
        raise RuntimeError("read-only corpus database hash changed after preregistration")
    profile = tomllib.loads((ROOT / "profiler" / "fiskehelse.toml").read_text(encoding="utf-8"))
    prefixes = tuple(profile.get("bank_proveniens", ()))
    if prefixes != tuple(prereg["corpus"]["provenance_prefixes"]):
        raise RuntimeError("profile allowlist changed after preregistration")
    conditions = " OR ".join("substr(proveniens,1,length(?))=?" for _ in prefixes)
    parameters = tuple(value for prefix in prefixes for value in (prefix, prefix))
    connection = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            f"SELECT id, bok, chunk_text FROM book_chunks WHERE {conditions} ORDER BY id",
            parameters,
        ).fetchall()
    finally:
        connection.close()
    corpus = [
        {"chunk_id": int(row[0]), "title": str(row[1] or ""), "text": str(row[2] or "")}
        for row in rows
        if str(row[2] or "").strip()
    ]
    if len(rows) != prereg["corpus"]["filtered_row_count"]:
        raise RuntimeError("filtered corpus row count does not match preregistration")
    if len(corpus) != prereg["corpus"]["nonempty_row_count"]:
        raise RuntimeError("non-empty corpus row count does not match preregistration")
    return corpus


def embed_one(text: str, task_prefix: str) -> tuple[list[float], int]:
    response = api_json(EMBED_URL, {
        "model": MODEL,
        "input": f"{task_prefix}{text}",
        "truncate": False,
        "options": {"num_ctx": CONTEXT_TOKENS},
        "keep_alive": "10m",
    })
    vectors = response.get("embeddings")
    token_count = response.get("prompt_eval_count")
    if response.get("model") != MODEL:
        raise RuntimeError("Ollama returned a different model name")
    if not isinstance(token_count, int):
        raise RuntimeError("Ollama did not return prompt_eval_count")
    if token_count > CONTEXT_TOKENS:
        raise RuntimeError("Ollama processed more tokens than the preregistered context limit")
    if not isinstance(vectors, list) or len(vectors) != 1:
        raise RuntimeError("Ollama returned an unexpected embedding batch")
    vector = vectors[0]
    if len(vector) != VECTOR_DIMENSIONS or not all(math.isfinite(float(value)) for value in vector):
        raise RuntimeError("Ollama returned a non-finite vector or unexpected dimensions")
    return [float(value) for value in vector], token_count


def unit_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm == 0:
        raise RuntimeError("embedding vector has an invalid norm")
    return [value / norm for value in values]


def vector_blob(values: list[float]) -> bytes:
    return sqlite_vec.serialize_float32(values)


def main() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if sha256_file(Path(__file__)) != prereg["executor_sha256"]:
        raise RuntimeError("executor changed after preregistration")
    if sha256_file(MODEL_BLOB) != prereg["model"]["blob_sha256"]:
        raise RuntimeError("local model blob hash changed after preregistration")
    version = api_json("http://127.0.0.1:11434/api/version").get("version")
    if version != prereg["ollama"]["version"]:
        raise RuntimeError("local Ollama version differs from preregistration")
    queries = load_queries(prereg)
    corpus = load_corpus(prereg)
    expected_counts = Counter(row["group"] for row in queries)
    if dict(expected_counts) != prereg["query_group_counts"]:
        raise RuntimeError("query groups do not match preregistration")
    print(f"local model={MODEL}; ollama={version}; corpus={len(corpus)}; queries={len(queries)}", flush=True)

    started = time.time()
    vectors: list[list[float]] = []
    input_records: list[dict[str, Any]] = []
    inputs = [("document", row, "search_document: ") for row in corpus]
    inputs.extend(("query", row, "search_query: ") for row in queries)
    for index, (kind, row, prefix) in enumerate(inputs, start=1):
        vector, token_count = embed_one(row["text"], prefix)
        raw_blob = vector_blob(vector)
        vectors.append(unit_vector(vector))
        input_records.append({
            "kind": kind,
            "id": row["chunk_id"] if kind == "document" else row["query_id"],
            "input_chars": len(prefix + row["text"]),
            "input_utf8_bytes": len((prefix + row["text"]).encode("utf-8")),
            "prompt_eval_count": token_count,
            "raw_embedding_sha256": sha256_bytes(raw_blob),
        })
        if index % 250 == 0 or index == len(inputs):
            print(f"embedded={index}/{len(inputs)}", flush=True)

    connection = sqlite3.connect(":memory:")
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    connection.execute("CREATE VIRTUAL TABLE screened_vectors USING vec0(row_id INTEGER PRIMARY KEY, embedding FLOAT[768])")
    connection.executemany(
        "INSERT INTO screened_vectors(row_id, embedding) VALUES (?, ?)",
        ((row["chunk_id"], vector_blob(vector)) for row, vector in zip(corpus, vectors[:len(corpus)])),
    )
    connection.commit()

    title_by_id = {row["chunk_id"]: row["title"] for row in corpus}
    records = []
    query_vectors = vectors[len(corpus):]
    for query, vector in zip(queries, query_vectors):
        neighbors = connection.execute(
            "SELECT row_id, distance FROM screened_vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (vector_blob(vector), TOP_K),
        ).fetchall()
        normalized_expected = normalized_title(query["expected_title"]) if query["expected_title"] else None
        ranks = [
            {
                "rank": rank,
                "chunk_id": int(chunk_id),
                "title_sha256": sha256_bytes(title_by_id[int(chunk_id)].encode("utf-8")),
                "distance_l2_unit_vectors": float(distance),
                "matches_expected_title": bool(
                    normalized_expected
                    and normalized_title(title_by_id[int(chunk_id)]) == normalized_expected
                ),
            }
            for rank, (chunk_id, distance) in enumerate(neighbors, start=1)
        ]
        records.append({
            "query_id": query["query_id"],
            "source_id": query["source_id"],
            "group": query["group"],
            "query_sha256": sha256_bytes(query["text"].encode("utf-8")),
            "expected_title_sha256": sha256_bytes(query["expected_title"].encode("utf-8")) if query["expected_title"] else None,
            "expected_title_present_in_corpus": bool(
                normalized_expected
                and any(normalized_title(title) == normalized_expected for title in title_by_id.values())
            ),
            "expected_title_hit_at_1": any(item["matches_expected_title"] for item in ranks[:1]),
            "expected_title_hit_at_5": any(item["matches_expected_title"] for item in ranks),
            "top5": ranks,
        })
    connection.close()

    covered = [row for row in records if row["group"] == "covered"]
    result = {
        "experiment_id": prereg["experiment_id"],
        "prereg_sha256": sha256_file(PREREG_PATH),
        "started_utc_epoch": started,
        "finished_utc_epoch": time.time(),
        "elapsed_seconds": round(time.time() - started, 3),
        "model": prereg["model"],
        "ollama": prereg["ollama"],
        "corpus": prereg["corpus"],
        "input_count": len(input_records),
        "query_count": len(records),
        "query_group_counts": dict(expected_counts),
        "prompt_token_count_summary": {
            kind: {
                "n": len(values),
                "min": min(values),
                "median": statistics.median(values),
                "max": max(values),
            }
            for kind in ("document", "query")
            for values in [[item["prompt_eval_count"] for item in input_records if item["kind"] == kind]]
        },
        "covered_expected_title_recall": {
            "n": len(covered),
            "corpus_target_present_n": sum(row["expected_title_present_in_corpus"] for row in covered),
            "hit_at_1_n": sum(row["expected_title_hit_at_1"] for row in covered),
            "hit_at_5_n": sum(row["expected_title_hit_at_5"] for row in covered),
        },
        "per_input": input_records,
        "per_query": records,
        "interpretation_limits": prereg["interpretation_limits"],
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"result={RESULT_PATH.relative_to(ROOT)}", flush=True)
    print(f"covered_hit_at_1={result['covered_expected_title_recall']['hit_at_1_n']}/{len(covered)}", flush=True)
    print(f"covered_hit_at_5={result['covered_expected_title_recall']['hit_at_5_n']}/{len(covered)}", flush=True)


if __name__ == "__main__":
    main()
