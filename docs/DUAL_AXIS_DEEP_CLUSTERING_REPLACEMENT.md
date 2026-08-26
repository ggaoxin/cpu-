# Dual-axis deep-clustering replacement

## Scope

This change replaces only the internal deep-clustering implementation. It does
not modify Vue, FastAPI route/controller files, MySQL schemas, or the existing
move-recognition, automatic-classification, keyword-recognition,
research-question, and citation-recognition implementations.

The public deep-clustering API is intentionally left unchanged for a later
front-end/back-end integration pass.

## Production routing

- `cluster_dimension=technology` routes to BGE-M3's native sparse head and a
  sparse cosine graph. It does not need GLM and does not use a topic library.
- `cluster_dimension=application_scenario` prefers an evidence-bound GLM
  extraction of three facets: application domain, real-world object, and
  real-world problem. BGE-M3 encodes these Core3 facets independently and
  concatenates them with weights `0.40/0.35/0.25`.
- The LLM extracts source-supported facets only. It never assigns cluster IDs,
  target K, or membership.
- If GLM is unavailable, the application route explicitly reports
  `local_fallback`. That path is useful for integration testing but its quality
  must not be reported as GLM-route benchmark performance.
- A fixed `cluster_count` uses the selected clustering family. Application
  `algorithm=auto` uses a symmetric kNN Louvain graph and falls back to the
  label-free eigengap/silhouette selector if Louvain is unavailable or
  degenerate.

## Input compatibility

The existing project contract is preserved. `SemanticRequest.texts` remains a
list of strings. The integration layer serializes structured documents as JSON
strings; the new service restores the following optional fields without making
them mandatory:

- `id` or `document_id`
- `publication_date`, `published_at`, `publication_year`, or `year`
- `text`, `content`, `abstract`, or `full_text`
- `title` and `keywords`

Generic scientific reports can therefore submit plain `text`; papers may add
metadata, but the algorithm does not require a paper-only schema.

## Main files

- `application/service/deep_clustering_service.py`: isolated application-layer
  orchestration and stable output assembly.
- `application/service/semantic_service.py`: the existing deep-clustering entry
  now forwards to the isolated service; its unreachable TopicFusion/private
  clustering methods were removed.
- `infrastructure/clustering/axis_router.py`: executes only the selected axis.
- `infrastructure/clustering/bge_m3_sparse.py`: technical-route engine.
- `infrastructure/clustering/application_dense.py`: application Core3 and
  fixed/automatic K engines.
- `infrastructure/clustering/axis_extractor.py`: evidence-bound GLM extraction
  with local fallback and audit metadata.
- `infrastructure/clustering/evidence_rule_engine.py`: bounded evidence
  expansion; rules never assign clusters.

## Verification

Run from the complete project root:

```bash
bash scripts/run_deep_clustering_selftests.sh
```

The local-model test loads the existing BGE-M3 directory. Model weights and API
keys are not part of the replacement package.

The following regression checks must also remain green:

```bash
python -m unittest tests.test_five_tool_http_integration
cd frontend && npm run build
```

The front-end build may report the pre-existing large-chunk warning; this is a
performance warning, not a build failure.

Historical TopicFusion directories are retained as inactive project archives
to avoid deleting user-owned research material. They are not imported by the
production `dc_cluster` call chain and are not included in the delivery ZIP.
