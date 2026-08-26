# Deep-clustering input representation v1

## Public Vue contract

Manual text input is always a list of objects containing:

```json
{"id":"DOC001","publication_date":"2025-01-01","text":"scientific text"}
```

`text` is required and is limited to 8,000 cleaned Unicode characters. The
front end prevents a longer manual value and the back end independently rejects
it. `publication_date` is retained for trend statistics and never enters the
BGE-M3 representation or clustering distance.

## Automatic representation modes

The system chooses a representation independently for every input item.

### Structured mode

Structured mode is used only when a real title, abstract, and at least two
keywords are all available. These may be supplied by a trusted file parser or
identified from explicit `Title/标题`, `Abstract/摘要`, and `Keywords/关键词`
labels inside `text`. All three fields must pass minimum completeness checks.

The initial technical source weights are title `0.15`, abstract `0.65`, and
keywords `0.20`. The initial application source weights are title `0.20`,
abstract `0.70`, and keywords `0.10`. Each source is encoded independently and
the vectors are combined numerically; text repetition is not used to imitate
weights.

For application clustering, source weights and Core3 weights are separate:
source weights identify where evidence came from, while domain `0.40`, object
`0.35`, and problem `0.25` identify the semantic composition of the scenario.

### Plain-text mode

If the full structure cannot be verified, the item uses `text` only. No title
is fabricated, no keywords are generated, and partial paper markers receive no
special weight. The complete text is split into bounded chunks, every chunk is
reviewed for the selected axis, and the strongest source-grounded chunks are
encoded and pooled. This prevents BGE-M3's token limit from silently reducing
an 8,000-character input to its beginning.

## Audit output

Every returned document includes `input_representation`, containing the mode,
parser, confidence, fields or chunks used, effective weights, source lengths,
and confirmation that publication time was not used for clustering. The same
audit object is also returned in `document_assignments` and the top-level
`input_representations` list.

## Scope

The change does not use a topic library and does not allow GLM or evidence
rules to assign cluster membership or target K. GLM remains an evidence-bound
application-facet extractor. Input representation, BGE-M3 encoding, and the
selected unsupervised clustering algorithm determine membership.
