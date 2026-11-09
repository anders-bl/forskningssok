"""Measure sensitivity of the frozen Nomic screen to exact-title caps."""
from __future__ import annotations

import collections
import hashlib
import hmac
import secrets
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import sqlite_vec
import offline_embedding_screen as base


ROOT = base.ROOT
PREREG = ROOT / "data/nomic_title_cap_sweep_prereg_2026-11-09.json"
RESULT = ROOT / "data/nomic_title_cap_sweep_results_2026-11-09.json"
CAPS = (0, 1, 2, 4)
INITIAL_K = 30
MAX_K = 4096


def sha(path: Path) -> str:
    return base.sha256_file(path)


def pseudonym(key: bytes, kind: str, value: Any) -> str:
    """Create an unlinkable, per-run reference without retaining the key."""
    message = f"{kind}:{value}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def main() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg.get("registered_before_inference") is not True:
        raise RuntimeError("archival sanitized record is not an executable preregistration")
    if sha(Path(__file__)) != prereg["executor_sha256"]:
        raise RuntimeError("executor changed after preregistration")
    if sha(base.MODEL_BLOB) != prereg["model"]["blob_sha256"]:
        raise RuntimeError("model blob changed")
    version = base.api_json("http://127.0.0.1:11434/api/version").get("version")
    if version != prereg["ollama"]["version"]:
        raise RuntimeError("Ollama version changed")
    queries, corpus = base.load_queries(prereg), base.load_corpus(prereg)
    if dict(collections.Counter(q["group"] for q in queries)) != prereg["query_group_counts"]:
        raise RuntimeError("query groups changed")

    started = time.time()
    redaction_key = secrets.token_bytes(32)
    documents: dict[int, list[float]] = {}
    query_vectors: dict[str, list[float]] = {}
    inputs: list[dict[str, Any]] = []
    all_inputs = [("document", row, "search_document: ") for row in corpus]
    all_inputs += [("query", row, "search_query: ") for row in queries]
    for i, (kind, row, prefix) in enumerate(all_inputs, 1):
        ident = row["chunk_id"] if kind == "document" else row["query_id"]
        full_text = prefix + row["text"]
        try:
            vector, tokens = base.embed_one(row["text"], prefix)
        except RuntimeError as error:
            if not base.is_context_rejection(error):
                raise
            inputs.append({"kind": kind, "input_ref": pseudonym(redaction_key, kind, ident), "input_chars": len(full_text),
                           "input_utf8_bytes": len(full_text.encode()),
                           "status": "rejected_over_context", "prompt_eval_count": None,
                           "error_ref": pseudonym(redaction_key, "error", base.sha256_bytes(str(error).encode()))})
            if i % 250 == 0 or i == len(all_inputs):
                print(f"embedded={i}/{len(all_inputs)}", flush=True)
            continue
        digest = base.sha256_bytes(base.vector_blob(vector))
        inputs.append({"kind": kind, "input_ref": pseudonym(redaction_key, kind, ident), "input_chars": len(full_text),
                       "input_utf8_bytes": len(full_text.encode()), "status": "embedded", "prompt_eval_count": tokens,
                       "embedding_ref": pseudonym(redaction_key, "embedding", digest)})
        if kind == "document":
            documents[int(ident)] = base.unit_vector(vector)
        else:
            query_vectors[str(ident)] = base.unit_vector(vector)
        if i % 250 == 0 or i == len(all_inputs):
            print(f"embedded={i}/{len(all_inputs)}", flush=True)

    db = sqlite3.connect(":memory:")
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("CREATE VIRTUAL TABLE vectors USING vec0(row_id INTEGER PRIMARY KEY, embedding FLOAT[768])")
    db.executemany("INSERT INTO vectors(row_id, embedding) VALUES (?, ?)",
                   ((r["chunk_id"], base.vector_blob(documents[r["chunk_id"]])) for r in corpus
                    if r["chunk_id"] in documents))
    db.commit()
    by_id = {r["chunk_id"]: r for r in corpus}
    per_query = []
    for q in queries:
        vector = query_vectors.get(q["query_id"])
        expected = base.normalized_title(q["expected_title"]) if q["expected_title"] else None
        policies = {}
        for cap in CAPS:
            if vector is None:
                policies[str(cap)] = {"search_k_used": 0, "top5": [], "hit_at_1": False, "hit_at_5": False}
                continue
            k = min(len(documents), INITIAL_K)
            max_k = min(len(documents), MAX_K)
            selected = []
            while True:
                neighbors = db.execute(
                    "SELECT row_id, distance FROM vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                    (base.vector_blob(vector), k)).fetchall()
                seen: dict[str, int] = {}
                selected = []
                for cid, dist in neighbors:
                    title = by_id[int(cid)]["title"]
                    n = seen.get(title, 0)
                    if cap and n >= cap:
                        continue
                    seen[title] = n + 1
                    selected.append((int(cid), float(dist)))
                    if len(selected) == base.TOP_K:
                        break
                if len(selected) == base.TOP_K or k >= max_k:
                    break
                k = min(max_k, k * 2)
            packed = []
            for rank, (cid, dist) in enumerate(selected, 1):
                title = by_id[cid]["title"]
                title_ref = pseudonym(redaction_key, "title", base.sha256_bytes(title.encode()))
                packed.append({"rank": rank, "candidate_ref": pseudonym(redaction_key, "document", cid),
                               "title_ref": title_ref,
                               "distance_l2_unit_vectors": dist,
                               "matches_expected_title": bool(expected and base.normalized_title(title) == expected)})
            policies[str(cap)] = {
                "search_k_used": k, "top5": packed,
                "hit_at_1": any(x["matches_expected_title"] for x in packed[:1]),
                "hit_at_5": any(x["matches_expected_title"] for x in packed),
            }
        per_query.append({"query_ref": pseudonym(redaction_key, "query", q["query_id"]), "group": q["group"],
                          "query_text_ref": pseudonym(redaction_key, "query-text", base.sha256_bytes(q["text"].encode())),
                          "expected_title_ref": pseudonym(redaction_key, "expected-title", base.sha256_bytes(q["expected_title"].encode())) if q["expected_title"] else None,
                          "expected_title_present_in_index": bool(expected and any(base.normalized_title(r["title"]) == expected for r in corpus)),
                          "policies": policies})
    db.close()
    covered = [q for q in per_query if q["group"] == "covered"]
    summaries = {}
    for cap in CAPS:
        key = str(cap)
        top1 = collections.Counter(q["policies"][key]["top5"][0]["title_ref"] for q in per_query if q["policies"][key]["top5"])
        slots = collections.Counter(x["title_ref"] for q in per_query for x in q["policies"][key]["top5"])
        summaries[key] = {
            "max_chunks_per_exact_title": cap or None,
            "covered_n": len(covered),
            "expected_title_hit_at_1_n": sum(q["policies"][key]["hit_at_1"] for q in covered),
            "expected_title_hit_at_5_n": sum(q["policies"][key]["hit_at_5"] for q in covered),
            "top1_distinct_title_count": len(top1),
            "largest_top1_title_frequency": max(top1.values(), default=0),
            "top5_distinct_title_count": len(slots),
            "largest_title_share_of_top5_slots": max(slots.values(), default=0) / max(1, len(per_query) * base.TOP_K),
            "queries_reaching_max_k": sum(q["policies"][key]["search_k_used"] == min(len(documents), MAX_K) for q in per_query),
        }
    out = {"experiment_id": prereg["experiment_id"], "prereg_sha256": sha(PREREG),
           "started_utc_epoch": started, "finished_utc_epoch": time.time(),
           "elapsed_seconds": round(time.time() - started, 3), "model": prereg["model"],
           "ollama": prereg["ollama"], "corpus": {**prereg["corpus"], "path": "<withheld; identify by sha256>", "indexed_chunk_count": len(documents),
                                                        "rejected_over_context_count": prereg["corpus"]["nonempty_row_count"]-len(documents)},
           "caps": list(CAPS), "policy_summary": summaries, "per_input": inputs,
           "per_query": per_query, "interpretation_limits": prereg["interpretation_limits"],
           "identifier_redaction": {"scheme": "one-time HMAC-SHA256", "key_retained": False,
                                    "purpose": "preserve within-result linkage without source identifiers"}}
    RESULT.write_text(json.dumps(out, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2), flush=True)
    print(f"result={RESULT}", flush=True)


if __name__ == "__main__":
    main()
