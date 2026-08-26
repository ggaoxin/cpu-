# Cluster Label Generation V1

## Scope

This implementation covers the algorithm-only stage requested by the client.
Its direct input is the phrase-set output of deep clustering. It does not read
raw documents, rerun clustering, query a database, or alter cluster membership.
Workflow orchestration for new uploads and historical tasks is intentionally
deferred to the later frontend/backend integration stage.

## Client input contract

- `cluster_phrase_sets`: required deep-clustering output. Each item contains a
  `cluster_id` and `phrases`.
- `label_length_limit`: optional; Chinese is counted by characters and English
  by words. Default: 12.
- `language_type`: optional `auto`, `zh`, or `en`. Default: `auto`.
- `distinctiveness_threshold`: optional value from 0 to 1. Default: 0.75.

The engine supports a single phrase set and a batch of phrase sets.

## Output contract

- `labels`: primary label, alternatives, evidence, coverage, confidence, and
  distinctiveness for each cluster.
- `generation_report`: preprocessing, candidate-generation, scoring, and
  selection audit.
- `label_differentiation_optimization`: before/after labels and threshold
  decisions for cross-cluster differentiation.

## Algorithm

1. Normalize the phrases supplied by deep clustering.
2. Build frequency-, n-gram-, and co-occurrence-based extractive candidates.
3. Optionally ask GLM for additional evidence-citing candidates.
4. Reject GLM candidates whose cited evidence cannot be found in the input.
5. Use BGE-M3 to score candidate-to-cluster relevance and cross-cluster margin.
6. Combine evidence support, relevance, distinctiveness, conciseness, and
   extractive weight.
7. Select labels globally and replace collisions with better differentiated
   alternatives.

There is no topic library, category catalogue, or Gold-label lookup in the
production path. Gold labels are used only by the offline evaluator.

## Gold construction protocol

Gold is manually assigned after deep clustering and before running the label
generator. GLM is not used to annotate Gold.

Every approved cluster passes three review rounds:

1. Evidence review: inspect representative phrases, centroid-nearest documents,
   and additional member titles; write the shortest label that covers the
   cluster's dominant semantic content.
2. Boundary review: compare the label against all other clusters on the same
   axis; record required concepts, acceptable equivalent labels, and forbidden
   over-broad or neighbouring concepts.
3. Terminology review: verify Chinese/English terminology, label length,
   grammatical completeness, and evidence traceability. Ambiguous clusters are
   marked pending and excluded from headline metrics.

The Gold file records review rounds, status, confidence, evidence document IDs,
and a locked `development` or `locked_test` split. Algorithm adjustments may use
the development split only; locked-test labels are not used for tuning.

## Evaluation metrics

- acceptable Top-1 accuracy;
- candidate recall at 5;
- required-concept precision, recall, and F1;
- BGE-M3 similarity to the Gold label and semantic pass rate;
- evidence-grounding and length-compliance rates;
- distinctiveness-threshold pass rate;
- duplicate-label rate.

Deep-clustering ARI is not a label-generation metric. It remains part of the
upstream clustering evaluation and must not be presented as label accuracy.

