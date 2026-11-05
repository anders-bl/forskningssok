"""Rerun the frozen embedding screen with the live per-title diversity cap.

The first R2402 pass ranked all chunks directly and exposed a large title with
813 of 4,732 rows. This pass applies the local retrieval path's cap of two
chunks per exact title before it reports the first five candidates.
"""
from __future__ import annotations

import collections
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import sqlite_vec

import offline_embedding_screen as base


PREREG_PATH = base.ROOT / "data" / "nomic_capped_screen_prereg_2026-11-05.json"
RESULT_PATH = base.ROOT / "data" / "nomic_capped_screen_results_2026-11-05.json"
PREVIOUS_RESULT_PATH = base.ROOT / "data" / "nomic_offline_screen_results_2026-11-05.json"
LIVE_POLICY_PATH = base.ROOT / "bank_bakgrunn.py"
MAX_PER_TITLE = 2
INITIAL_K_MULTIPLIER = 6
MAX_KNN = 4096


def main() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if base.sha256_file(Path(__file__)) != prereg["executor_sha256"]:
        raise RuntimeError("capped-screen executor changed after preregistration")
    if base.sha256_file(LIVE_POLICY_PATH) != prereg["live_policy"]["sha256"]:
        raise RuntimeError("live retrieval policy changed after preregistration")
    if base.sha256_file(PREVIOUS_RESULT_PATH) != prereg["previous_result_sha256"]:
        raise RuntimeError("previous screening result changed after preregistration")
    previous = json.loads(PREVIOUS_RESULT_PATH.read_text(encoding="utf-8"))
    previous_inputs = {
        (item["kind"], str(item["id"])): item["raw_embedding_sha256"]
        for item in previous["per_input"] if item.get("raw_embedding_sha256")
    }
    previous_queries = {item["query_id"]: item for item in previous["per_query"]}
    if base.sha256_file(base.MODEL_BLOB) != prereg["model"]["blob_sha256"]:
        raise RuntimeError("local model blob changed after preregistration")
    version = base.api_json("http://127.0.0.1:11434/api/version").get("version")
    if version != prereg["ollama"]["version"]:
        raise RuntimeError("local Ollama version differs from preregistration")
    queries = base.load_queries(prereg)
    corpus = base.load_corpus(prereg)
    counts = collections.Counter(row["group"] for row in queries)
    if dict(counts) != prereg["query_group_counts"]:
        raise RuntimeError("query groups do not match preregistration")

    started = time.time()
    document_vectors: dict[int, list[float]] = {}
    query_vectors: dict[str, list[float]] = {}
    input_records: list[dict[str, Any]] = []
    inputs = [("document", row, "search_document: ") for row in corpus]
    inputs.extend(("query", row, "search_query: ") for row in queries)
    same_embedding_hashes = 0
    for index, (kind, row, prefix) in enumerate(inputs, start=1):
        identity = row["chunk_id"] if kind == "document" else row["query_id"]
        text = prefix + row["text"]
        record: dict[str, Any] = {
            "kind": kind,
            "id": identity,
            "input_chars": len(text),
            "input_utf8_bytes": len(text.encode("utf-8")),
        }
        try:
            vector, token_count = base.embed_one(row["text"], prefix)
        except RuntimeError as error:
            if not base.is_context_rejection(error):
                raise
            record.update({
                "status": "rejected_over_context",
                "prompt_eval_count": None,
                "error_sha256": base.sha256_bytes(str(error).encode("utf-8")),
            })
        else:
            blob = base.vector_blob(vector)
            vector_hash = base.sha256_bytes(blob)
            prior_hash = previous_inputs.get((kind, str(identity)))
            same_embedding_hashes += prior_hash == vector_hash
            record.update({
                "status": "embedded",
                "prompt_eval_count": token_count,
                "raw_embedding_sha256": vector_hash,
                "matches_previous_embedding_hash": prior_hash == vector_hash,
            })
            normalized = base.unit_vector(vector)
            if kind == "document":
                document_vectors[int(identity)] = normalized
            else:
                query_vectors[str(identity)] = normalized
        input_records.append(record)
        if index % 250 == 0 or index == len(inputs):
            print(f"embedded={index}/{len(inputs)}", flush=True)

    connection = sqlite3.connect(":memory:")
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    connection.execute("CREATE VIRTUAL TABLE screened_vectors USING vec0(row_id INTEGER PRIMARY KEY, embedding FLOAT[768])")
    connection.executemany(
        "INSERT INTO screened_vectors(row_id, embedding) VALUES (?, ?)",
        ((row["chunk_id"], base.vector_blob(document_vectors[row["chunk_id"]]))
         for row in corpus if row["chunk_id"] in document_vectors),
    )
    connection.commit()
    by_id = {row["chunk_id"]: row for row in corpus}
    per_query = []
    for query in queries:
        vector = query_vectors.get(query["query_id"])
        raw_rows = []
        capped_rows = []
        search_k = min(len(document_vectors), max(base.TOP_K * INITIAL_K_MULTIPLIER, base.TOP_K))
        if vector is not None:
            max_k = min(len(document_vectors), MAX_KNN)
            while True:
                raw_rows = connection.execute(
                    "SELECT row_id, distance FROM screened_vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                    (base.vector_blob(vector), search_k),
                ).fetchall()
                per_title: dict[str, int] = {}
                capped_rows = []
                for chunk_id, distance in raw_rows:
                    title = by_id[int(chunk_id)]["title"]
                    if per_title.get(title, 0) >= MAX_PER_TITLE:
                        continue
                    per_title[title] = per_title.get(title, 0) + 1
                    capped_rows.append((int(chunk_id), float(distance)))
                    if len(capped_rows) >= base.TOP_K:
                        break
                if len(capped_rows) >= base.TOP_K or search_k >= max_k:
                    break
                search_k = min(max_k, search_k * 2)
        normalized_expected = base.normalized_title(query["expected_title"]) if query["expected_title"] else None

        def pack(rows: list[tuple[int, float]]) -> list[dict[str, Any]]:
            packed = []
            for rank, (chunk_id, distance) in enumerate(rows, start=1):
                title = by_id[chunk_id]["title"]
                packed.append({
                    "rank": rank,
                    "chunk_id": chunk_id,
                    "title_sha256": base.sha256_bytes(title.encode("utf-8")),
                    "distance_l2_unit_vectors": distance,
                    "matches_expected_title": bool(
                        normalized_expected and base.normalized_title(title) == normalized_expected
                    ),
                })
            return packed

        raw_top5 = pack([(int(cid), float(dist)) for cid, dist in raw_rows[:base.TOP_K]])
        capped_top5 = pack(capped_rows)
        prior_query = previous_queries[query["query_id"]]
        prior_ids = [entry["chunk_id"] for entry in prior_query["top5"]]
        raw_ids = [entry["chunk_id"] for entry in raw_top5]
        target_present = bool(normalized_expected and any(
            base.normalized_title(row["title"]) == normalized_expected
            for row in corpus if row["chunk_id"] in document_vectors
        ))
        per_query.append({
            "query_id": query["query_id"],
            "source_id": query["source_id"],
            "group": query["group"],
            "status": "embedded" if vector is not None else "rejected_over_context",
            "query_sha256": base.sha256_bytes(query["text"].encode("utf-8")),
            "expected_title_sha256": base.sha256_bytes(query["expected_title"].encode("utf-8")) if query["expected_title"] else None,
            "expected_title_present_in_index": target_present,
            "raw_top5_exactly_matches_previous": raw_ids == prior_ids,
            "raw_top5_shared_ids_with_previous": len(set(raw_ids) & set(prior_ids)),
            "search_k_used": search_k if vector is not None else 0,
            "capped_distinct_title_count": len({item["title_sha256"] for item in capped_top5}),
            "raw_top5": raw_top5,
            "capped_top5": capped_top5,
            "expected_title_hit_at_1": any(item["matches_expected_title"] for item in capped_top5[:1]),
            "expected_title_hit_at_5": any(item["matches_expected_title"] for item in capped_top5),
        })
    connection.close()

    covered = [row for row in per_query if row["group"] == "covered"]
    top1_counts = collections.Counter(row["capped_top5"][0]["title_sha256"] for row in per_query if row["capped_top5"])
    title_slots = collections.Counter(item["title_sha256"] for row in per_query for item in row["capped_top5"])
    token_summary = {}
    for kind in ("document", "query"):
        values = [item["prompt_eval_count"] for item in input_records
                  if item["kind"] == kind and item["prompt_eval_count"] is not None]
        token_summary[kind] = {
            "n": len(values),
            "min": min(values) if values else None,
            "median": __import__("statistics").median(values) if values else None,
            "max": max(values) if values else None,
        }
    result = {
        "experiment_id": prereg["experiment_id"],
        "prereg_sha256": base.sha256_file(PREREG_PATH),
        "previous_result_sha256": prereg["previous_result_sha256"],
        "started_utc_epoch": started,
        "finished_utc_epoch": time.time(),
        "elapsed_seconds": round(time.time() - started, 3),
        "model": prereg["model"],
        "ollama": prereg["ollama"],
        "corpus": {
            **prereg["corpus"],
            "indexed_chunk_count": len(document_vectors),
            "rejected_over_context_count": len(corpus) - len(document_vectors),
        },
        "live_policy": prereg["live_policy"],
        "input_count": len(input_records),
        "input_status_counts": dict(collections.Counter(item["status"] for item in input_records)),
        "query_count": len(per_query),
        "query_group_counts": dict(counts),
        "prompt_token_count_summary": token_summary,
        "embedding_hash_reproduction": {
            "same_hashes": same_embedding_hashes,
            "compared_inputs": sum(item["status"] == "embedded" for item in input_records),
        },
        "raw_top5_reproduction": {
            "exact_same_query_lists": sum(item["raw_top5_exactly_matches_previous"] for item in per_query),
            "queries": len(per_query),
        },
        "capped_retrieval_summary": {
            "max_chunks_per_exact_title": MAX_PER_TITLE,
            "covered_query_count": len(covered),
            "expected_title_in_index_n": sum(item["expected_title_present_in_index"] for item in covered),
            "expected_title_hit_at_1_n": sum(item["expected_title_hit_at_1"] for item in covered),
            "expected_title_hit_at_5_n": sum(item["expected_title_hit_at_5"] for item in covered),
            "top1_distinct_title_count": len(top1_counts),
            "largest_top1_title_frequency": max(top1_counts.values()) if top1_counts else 0,
            "top5_title_slots": len(per_query) * base.TOP_K,
            "largest_title_share_of_top5_slots": max(title_slots.values()) / (len(per_query) * base.TOP_K),
        },
        "per_input": input_records,
        "per_query": per_query,
        "interpretation_limits": prereg["interpretation_limits"],
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"result={RESULT_PATH.relative_to(base.ROOT)}", flush=True)
    print(f"capped_covered_hit_at_1={result['capped_retrieval_summary']['expected_title_hit_at_1_n']}/{len(covered)}", flush=True)
    print(f"capped_covered_hit_at_5={result['capped_retrieval_summary']['expected_title_hit_at_5_n']}/{len(covered)}", flush=True)
    print(f"raw_top5_reproduced={result['raw_top5_reproduction']['exact_same_query_lists']}/{len(per_query)}", flush=True)


if __name__ == "__main__":
    main()
