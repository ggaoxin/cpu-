# Cluster Label Generation Verification V1

## Outcome

The production cluster-label generator is implemented under
`infrastructure/cluster_labeling`. It consumes deep-clustering phrase sets,
does not map to a predefined topic library, and does not change cluster
membership.

The recommended production mode is `hybrid`: GLM proposes evidence-citing
candidates and BGE-M3 performs evidence validation, relevance scoring and
cross-cluster differentiation. `local` mode is a deterministic offline
fallback and is the mode verified in this report because the current local
execution environment could not reach the configured GLM endpoint.

## Evaluation data and Gold lock

- Source data: all 1,000 Chinese and 1,000 English records supplied by the
  client.
- Evaluation benchmark: 16 technology-route clusters and 16 application-scene
  clusters, with Chinese and English represented equally on each axis.
- Gold authoring: manual semantic review by Codex; GLM and other API models
  were not used to assign Gold labels.
- Review: evidence, boundary and terminology review, three rounds per cluster.
- Split per axis: 12 development clusters and 4 locked-test clusters.
- Gold was SHA-256 locked before any prediction was generated. The lock is in
  `eval/cluster_labeling/gold/gold_lock_v1.json` and can be checked with
  `scripts/verify_cluster_label_gold_lock.py`.

The evidence selectors used to assemble this benchmark live only under
`eval/cluster_labeling`; production code does not import them and they are not
a production topic library.

## Final local BGE-M3 results

Semantic pass uses a predeclared BGE-M3 cosine threshold of 0.70. Exact string
accuracy is reported, but concept F1 and semantic similarity are more useful
for cluster labels because multiple concise phrasings can be correct.

### Overall benchmark

| Axis | Clusters | Concept precision | Concept recall | Concept F1 | Mean semantic similarity | Semantic pass | Evidence grounded | Length compliant | Duplicate labels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Technology route | 16 | 1.000 | 0.781 | 0.877 | 0.784 | 0.750 | 1.000 | 1.000 | 0.000 |
| Application scene | 16 | 1.000 | 0.750 | 0.857 | 0.725 | 0.563 | 1.000 | 1.000 | 0.000 |

### Locked test only

| Axis | Clusters | Concept precision | Concept recall | Concept F1 | Mean semantic similarity | Semantic pass | Evidence grounded | Length compliant | Duplicate labels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Technology route | 4 | 1.000 | 0.750 | 0.857 | 0.775 | 0.750 | 1.000 | 1.000 | 0.000 |
| Application scene | 4 | 1.000 | 0.875 | 0.933 | 0.736 | 0.750 | 1.000 | 1.000 | 0.000 |

The locked-test Gold was not changed during tuning. Development results were
used to improve general phrase fusion, evidence breadth, morphological
deduplication, readable conjunctions and BGE-M3 margin calibration.

## Baseline-to-final change

At the same 0.70 semantic threshold:

- Technology-route overall concept F1 improved from 0.667 to 0.877; mean
  semantic similarity improved from 0.705 to 0.784.
- Application-scene overall concept F1 improved from 0.720 to 0.857; mean
  semantic similarity improved from 0.651 to 0.725.
- Both axes retained 100% evidence grounding, 100% label-length compliance and
  zero duplicate labels.

## Interpretation and remaining limitation

The deterministic local engine is a sound engineering fallback. Its remaining
weakness is conservative abstraction: when input phrases list several specific
objects but omit an explicit umbrella term, the local engine will not invent
that umbrella term. This is visible mainly in English application-scene labels.

Hybrid mode addresses this gap without using a topic library. GLM may propose a
conservative abstraction only when it cites two to five supplied phrases; the
candidate then receives no special trust and must pass BGE-M3 relevance,
evidence, length and differentiation checks. If GLM fails, generation continues
with the verified local path and records the failure in `generation_report`.

## Reproduction

Run from the project root:

```powershell
python scripts/verify_cluster_label_gold_lock.py
python scripts/run_cluster_label_generation_experiment.py --input eval/cluster_labeling/gold_sources/technology_gold_sources.json --output eval/cluster_labeling/predictions/technology_local_v5.json --label-length-limit 12 --language-type auto --distinctiveness-threshold 0.75
python scripts/evaluate_cluster_labels.py --predictions eval/cluster_labeling/predictions/technology_local_v5.json --gold eval/cluster_labeling/gold/technology_gold_v1.json --output eval/cluster_labeling/reports/technology_local_v5_metrics.json --semantic --semantic-threshold 0.70
```

Repeat the last two commands with the application files for the application
axis. Add `--use-glm` to the generation command on a server that can reach the
configured GLM endpoint to verify hybrid-mode uplift.
