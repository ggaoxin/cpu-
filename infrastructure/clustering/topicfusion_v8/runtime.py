from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from ..topicfusion_v7.runtime import load_input
from .memory import map_documents

def run_mapping(input_file: str, output_dir: str, root: str | None = None, top_k: int = 3):
    rootp=Path(root) if root else Path(__file__).resolve().parents[1]
    df=load_input(input_file)
    out=map_documents(df,rootp,top_k=top_k)
    od=Path(output_dir); od.mkdir(parents=True,exist_ok=True)
    csv=od/'dual_topic_mapping_results_v8.csv'; js=od/'dual_topic_mapping_results_v8.json'
    out.to_csv(csv,index=False,encoding='utf-8-sig'); out.to_json(js,orient='records',force_ascii=False,indent=2)
    candidates=out[(out.technical_mapping_status=='candidate_new_topic')|(out.application_mapping_status=='candidate_new_topic')]
    candidates.to_json(od/'new_topic_candidates.jsonl',orient='records',force_ascii=False,lines=True)
    metadata = {
        'version': '8.1',
        'input_file': str(input_file),
        'documents': int(len(out)),
        'languages': {str(k): int(v) for k, v in out.language.value_counts().items()},
        'technical_statuses': {str(k): int(v) for k, v in out.technical_mapping_status.value_counts().items()},
        'application_statuses': {str(k): int(v) for k, v in out.application_mapping_status.value_counts().items()},
        'candidate_documents': int(len(candidates)),
        'top_k': int(top_k),
    }
    (od/'run_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return csv
