from __future__ import annotations
import json,re
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import numpy as np,pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sklearn.linear_model import SGDClassifier
from sklearn.metrics.pairwise import cosine_similarity

@dataclass
class Config:
    input_file:str
    taxonomy_file:str
    output_dir:str='results'
    calibration_file:str|None=None
    random_state:int=42
    svd_dim:int=120

METHOD_RE=re.compile(r'\b(propos|present|introduc|develop|design|deriv|employ|use|evaluat|assess|investigat|conduct|method|approach|framework|model|algorithm|technique|experiment|assay|simulation|analysis|measurement|synthesi|fabricat|polymeri|randomi|retrospective|prospective|review|case report|cohort|survey|pcr|western blot|immunohistochem|spectroscop|microscop|sequenc|genotyp|photo.?trap|field sampl)\w*\b',re.I)
APP_RE=re.compile(r'\b(aim|purpose|objective|application|patient|disease|treatment|diagnos|health|material|device|energy|environment|water|soil|plant|animal|cancer|cardiac|battery|sensor|antenna|transport|policy|education|ecolog|wildlife|veterinary)\w*\b',re.I)

def clean(v:Any)->str:
    s='' if v is None else str(v)
    s=re.sub(r'<[^>]+>|https?://\S+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def sentences(s:str)->list[str]:
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+',s) if len(x.strip())>=20]

def kw_text(v:Any)->str:
    if isinstance(v,list): return '; '.join(map(str,v))
    return clean(v)

def extract_views(title:str,abstract:str,keywords:list[str])->tuple[str,str]:
    ss=sentences(abstract); kws=kw_text(keywords)
    method=[s for s in ss if METHOD_RE.search(s)] or ss[:4]
    app=[s for i,s in enumerate(ss) if i<3 or APP_RE.search(s)] or ss[:4]
    # Field markers help preserve source semantics while title repetition raises task/object salience.
    tech=f"[TITLE] {title} [KEYWORDS] {kws} [METHOD] {' '.join(method[:9])}"
    appl=f"[TITLE] {title} [TITLE] {title} [KEYWORDS] {kws} [OBJECTIVE_CONTEXT] {' '.join(app[:8])}"
    return clean(tech),clean(appl)

def load(path:str)->pd.DataFrame:
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(obj,dict): obj=obj.get('documents',obj.get('data',[]))
    df=pd.DataFrame(obj)
    if 'document_id' not in df: df['document_id']=[f'DOC_{i:04d}' for i in range(1,len(df)+1)]
    for c in ['en_name','en_abstract']:
        if c not in df: raise ValueError(f'missing {c}')
        df[c]=df[c].map(clean)
    if 'keywords' not in df: df['keywords']=[[] for _ in range(len(df))]
    views=df.apply(lambda r:extract_views(r.en_name,r.en_abstract,r.keywords),axis=1)
    df[['technical_route_text','application_scenario_text']]=pd.DataFrame(views.tolist(),index=df.index)
    df['full_text']=df.en_name+' '+df.keywords.map(kw_text)+' '+df.en_abstract
    return df

def vectorizer(max_features=24000)->FeatureUnion:
    return FeatureUnion([
      ('word',TfidfVectorizer(stop_words='english',ngram_range=(1,3),min_df=1,max_df=.98,sublinear_tf=True,max_features=int(max_features*.72))),
      ('char',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,sublinear_tf=True,max_features=int(max_features*.28)))
    ],transformer_weights={'word':.80,'char':.20})

# Rule library is intentionally boundary-oriented: positive evidence, negative evidence, and precedence.
TECH_RULES={
'T04':[(r'\brandomi[sz]ed controlled trial\b|\bdouble[- ]blind\b|\bplacebo[- ]controlled\b',4.0)],
'T05':[(r'\bsystematic review\b|\bmeta[- ]analysis\b|\bPRISMA\b|pooled analysis',4.2)],
'T07':[(r'\bcase report\b|\bcase series\b|report of (two|three|four|five|six|seven|eight|nine|ten) cases|case history',4.0)],
'T06':[(r'\bnarrative review\b|\bperspective\b|\bcommentary\b|comprehensive review|literature review|we review|this review',2.8)],
'T03':[(r'\bretrospective\b|\bprospective cohort\b|\bcross-sectional\b|population-based|registry study|case-control|survival analysis|Cox regression',3.2)],
'T20':[(r'questionnaire|focus group|semi-structured interview|qualitative study|survey of|knowledge.*attitude',3.3)],
'T21':[(r'cost-effectiveness|cost-utility|time trade-off|economic evaluation|dynamic efficiency|health state utilit',4.0)],
'T29':[(r'photo[- ]trapping|field sampling|ecological survey|habitat survey|wildlife monitoring|vegetation survey|transect',4.0)],
'T30':[(r'health risk assessment|ecological risk|source apportionment|spatial distribution|geospatial|GIS|exposure assessment',3.6)],
'T33':[(r'growth performance|feeding trial|behavioral test|swimming performance|reproductive performance|physiological comparison',3.0)],
'T22':[(r'\b(rats?|mice|murine|rabbit|beagle|canine|zebrafish|tilapia|animal model)\b.*\b(treatment|administer|injected|induced|dose|supplement)',3.5),(r'\bin vivo\b',1.3)],
'T09':[(r'RNA[- ]seq|single[- ]cell RNA|transcriptom|proteom|metabolom|whole[- ]genome|next[- ]generation sequencing|bioinformatics',4.0)],
'T23':[(r'metagenom|microbiome|microbial community|bacterial culture|antimicrobial susceptibility|16S rRNA',3.7)],
'T24':[(r'\bPCR\b|qRT-PCR|qPCR|genotyp|polymorphism|Mendelian randomization|gene variant|restriction fragment length',3.0)],
'T10':[(r'immunohistochem|histopatholog|histomorpholog|tissue staining|pathological diagnosis',3.4)],
'T11':[(r'medical imaging|diagnostic ultrasound|Doppler|\bMRI\b|magnetic resonance imaging|CT scan|computed tomography|X-ray imaging|electrocardiogram|\bECG\b|physiological measurement',2.7)],
'T15':[(r'first[- ]principles|density functional theory|\bDFT\b|molecular dynamics|ab initio|phonon calculation|atomistic simulation',4.2)],
'T14':[(r'finite element|computational fluid dynamics|Monte Carlo|numerical simulation|microstructural model|device simulation',3.6)],
'T16':[(r'analytical solution|asymptotic|mathematical model|theoretical derivation|kinetic model|governing equation',2.5)],
'T17':[(r'antenna|waveguide|power divider|photodetector|device prototype|prototype (was )?fabricated|fabricated and measured|circuit design',3.8)],
'T26':[(r'model predictive control|trajectory planning|autonomous navigation|robotic|tracking controller|control framework',3.7)],
'T27':[(r'image processing|signal processing|reconstruction algorithm|segmentation algorithm|feature extraction|compression algorithm',2.8)],
'T19':[(r'wastewater treatment|membrane bioreactor|resource recovery|remediation process|adsorption removal',3.4)],
'T18':[(r'catalyst|catalytic conversion|electrocatal|photocatal|cross-coupling|organic synthesis|chemical reaction mechanism',3.2)],
'T12':[(r'we (synthesi[sz]ed|prepared|fabricated|developed)|was synthesized|were synthesized|hydrothermal|polymeri[sz]ation|deposition|annealing|electrospinning|doping|coating',3.4)],
'T13':[(r'characteri[sz]ation study|characteri[sz]ed by|\bXRD\b|\bSEM\b|\bTEM\b|Raman spectroscopy|FTIR|impedance spectroscopy|mechanical testing|direct shear test',1.35)],
'T31':[(r'chromatograph|mass spectrom|HPLC|GC-MS|quantitative determination|physicochemical analysis|antioxidant assay',3.2)],
'T08':[(r'cell culture|western blot|apoptosis|signaling pathway|\bin vitro\b|cellular experiment|protein expression',2.5)],
'T25':[(r'dataset|benchmark|database|tool validation|protocol validation|nomogram|risk score|instrument validation',2.5)],
'T32':[(r'system architecture|integrated system|configuration optimization|design procedure|energy management system|engineering framework',2.8)],
'T02':[(r'support vector machine|random forest|decision tree|logistic regression|machine learning|statistical model|principal component analysis|clustering',2.4)],
'T01':[(r'deep learning|neural network|transformer|convolutional network|U-Net|GAN|autoencoder|attention model',2.6)],
}
APP_RULES={
'A01':[(r'cardiovascular|cardiac|heart|hypertension|atrial fibrillation|myocardial|aortic|vascular|thrombosis|coronary|stroke',3.2)],
'A02':[(r'endocrine|metabolic|diabetes|obesity|thyroid|Cushing|adrenal|polycystic ovarian|glucose|insulin',3.1)],
'A03':[(r'cancer|tumou?r|carcinoma|oncology|metastasis|chemotherapy|radiotherapy|leukemia|lymphoma',3.2)],
'A04':[(r'psychiatr|mental health|depression|PTSD|dementia|Parkinson|schizophrenia|cognitive disorder|neurolog',3.1)],
'A05':[(r'fracture|orthopedic|osteoarthritis|bone|joint|arthroplasty|musculoskeletal|rehabilitation|mandibular',3.1)],
'A06':[(r'liver|hepatic|intestinal|gastrointestinal|bowel|colon|colorectal|pancrea|constipation|renal|kidney',3.0)],
'A07':[(r'infection|bacteri|virus|viral|antimicrobial resistance|pathogen|COVID|sepsis',3.0)],
'A08':[(r'pediatric|children|pregnancy|preeclampsia|menstrual|reproductive|neonatal|maternal|fertility',3.0)],
'A09':[(r'medical imaging|diagnostic imaging|ultrasound probe|MRI segmentation|CT imaging|clinical monitoring device|surgical instrument',3.3)],
'A10':[(r'public health|nursing|healthcare service|quality of life|patient management|screening program|health system',2.6)],
'A11':[(r'veterinary|canine|dog|wildcat|cat |tilapia|aquaculture|livestock|animal health',3.7)],
'A12':[(r'ecology|species|biodiversity|conservation|crop|forest|wildlife|agriculture|seed|soil biology',3.3)],
'A13':[(r'wastewater|water treatment|pollution|remediation|contamination|groundwater|waste resource recovery',3.4)],
'A14':[(r'battery|energy storage|solar cell|photovoltaic|fuel cell|hydrogen energy|microgrid|electrolyte|cathode|anode',3.5)],
'A15':[(r'polymer|composite|alloy|ceramic|structural material|mechanical properties|coating|hydrogel|asphalt|concrete',3.0)],
'A16':[(r'semiconductor|photodetector|electronic device|sensor|flexible electronics|transistor|optoelectronic|microelectrode',3.4)],
'A17':[(r'antenna|waveguide|laser|photonic|optical communication|metasurface|holographic|terahertz|microwave|orbital angular momentum',3.5)],
'A18':[(r'geotechnical|pavement|subgrade|civil infrastructure|railway|highway|bridge',3.5)],
'A19':[(r'mechanical manufacturing|machining|compressor|engine|industrial equipment|heat transfer equipment',3.0)],
'A20':[(r'robotic|autonomous control|navigation|trajectory|surgical robot|unmanned system',3.5)],
'A21':[(r'CO2 capture|CO2 conversion|catalysis|electrocatalysis|photocatalysis|carbon fixation',3.5)],
'A22':[(r'gene|DNA|RNA|transcription factor|protein|cell signaling|molecular biology|genetics|epigenetics',2.4)],
'A23':[(r'food|nutrition|antioxidant|phytochemical|natural product|dietary|fruit|vegetable|probiotic',2.7)],
'A24':[(r'economics|policy|social welfare|gender|religion|law|governance|rights|insurance|austerity',3.3)],
'A25':[(r'education|training|students|curriculum|internship|competence|teaching|research program',3.2)],
'A26':[(r'artificial intelligence|machine learning|computer vision|natural language processing|software|algorithm|data analytics',2.8)],
'A27':[(r'physics|quantum|statistical mechanics|thermodynamics|entropy|fundamental science',3.0)],
'A28':[(r'climate|geology|earthquake|landslide|atmosphere|ocean|global warming|hydrology|meteorology',3.3)],
'A29':[(r'drug delivery|liposome|pharmaceutical formulation|nanomedicine|bioavailability|therapeutic carrier',3.5)],
}

def rule_scores(df:pd.DataFrame,axis_ids:list[str],dimension:str)->np.ndarray:
    rules=TECH_RULES if dimension=='technical' else APP_RULES
    scores=np.zeros((len(df),len(axis_ids)),dtype=float); pos={x:i for i,x in enumerate(axis_ids)}
    for r_idx,row in df.iterrows():
        title=clean(row.en_name); kw=kw_text(row.keywords); abstract=clean(row.en_abstract)
        fields=[(title,1.45),(kw,1.25),(abstract,1.0)]
        for cid,patterns in rules.items():
            if cid not in pos: continue
            for pat,w in patterns:
                for text,mult in fields:
                    if re.search(pat,text,re.I): scores[r_idx,pos[cid]]+=w*mult
    return scores

def boundary_adjust(df:pd.DataFrame,ids:list[str],scores:np.ndarray,dimension:str)->np.ndarray:
    idx={x:i for i,x in enumerate(ids)}; s=scores.copy()
    def add(row,cid,val):
        if cid in idx: s[row,idx[cid]]+=val
    for i,r in df.iterrows():
        t=(clean(r.en_name)+' '+kw_text(r.keywords)+' '+clean(r.en_abstract)).lower()
        if dimension=='technical':
            # Document-design precedence.
            if re.search(r'systematic review|meta-analysis|prisma',t): add(i,'T05',5); add(i,'T06',-2); add(i,'T03',-2)
            elif re.search(r'case report|case series|case history|report of (two|three|four|five|six|seven|eight|nine|ten) cases',t): add(i,'T07',5); add(i,'T10',-1.5); add(i,'T03',-1)
            elif re.search(r'randomi[sz]ed controlled trial|double-blind|placebo-controlled',t) and re.search(r'patients|participants|children|women|men|subjects',t): add(i,'T04',5); add(i,'T03',-2); add(i,'T22',-2)
            # Materials synthesis vs characterization: contribution verb wins over instrument list.
            syn=bool(re.search(r'we (synthesi[sz]ed|prepared|fabricated|developed)|was synthesized|were synthesized|hydrothermal|polymeri[sz]ation|deposition|annealing|electrospinning',t))
            char=bool(re.search(r'characteri[sz]ed by|xrd|sem|tem|raman|ftir|impedance spectroscopy|mechanical testing|direct shear test',t))
            if syn: add(i,'T12',3.5); add(i,'T13',-1.2)
            elif char: add(i,'T13',1.7)
            # Animal/in-vivo overrides molecular assays when the intervention unit is an animal.
            animal=bool(re.search(r'\b(rats?|mice|murine|rabbit|beagle|canine|tilapia|zebrafish|animal model)\b',t))
            intervention=bool(re.search(r'administer|injected|treated|supplement|induced|dose|feeding trial|in vivo',t))
            if animal and intervention: add(i,'T22',3.6); add(i,'T08',-1.5)
            elif re.search(r'cell culture|primary cells|in vitro|western blot',t): add(i,'T08',2.5)
            # Omics is broad profiling; PCR/genotyping is targeted molecular detection.
            if re.search(r'rna-seq|transcriptom|proteom|metabolom|single-cell|whole-genome|next-generation sequencing',t): add(i,'T09',4); add(i,'T24',-1.5)
            elif re.search(r'\bpcr\b|qrt-pcr|qpcr|genotyp|polymorphism|gene variant',t): add(i,'T24',3)
            # Built prototype beats simulation; simulation wins only when no fabrication/measurement.
            built=bool(re.search(r'prototype|fabricated and measured|prototype is fabricated|measurements demonstrate|device was fabricated',t))
            sim=bool(re.search(r'finite element|numerical simulation|computational fluid dynamics|monte carlo',t))
            if built: add(i,'T17',3.5); add(i,'T14',-1.5)
            elif sim: add(i,'T14',3)
            # Clinical cohort vs imaging method: cohort/outcome question wins unless a new diagnostic technique is the contribution.
            cohort=bool(re.search(r'retrospective|prospective|cross-sectional|population-based|cohort|survival|risk factors|cox regression',t))
            newdiag=bool(re.search(r'we propose|novel.*(diagnostic ultrasound|mri|medical imaging|diagnostic)|diagnostic accuracy|sensitivity and specificity',t))
            if cohort and not newdiag: add(i,'T03',2.8); add(i,'T11',-1.0)
            # Catalytic chemistry vs generic material synthesis.
            if re.search(r'catalytic conversion|catalyst|electrocatal|photocatal|cross-coupling',t): add(i,'T18',3); add(i,'T12',-0.7)
        else:
            # Disease domain vs diagnostic technology.
            disease=bool(re.search(r'cardiovascular|cardiac|hypertension|cancer|tumou?r|diabetes|liver|intestinal|psychiatr|osteoarthritis',t))
            technique_core=bool(re.search(r'novel.*(imaging|ultrasound|mri|device)|develop.*(probe|device|diagnostic method)|segmentation|image reconstruction',t))
            if disease and not technique_core: add(i,'A09',-1.2)
            if technique_core: add(i,'A09',2.8)
            # Human disease vs veterinary.
            if re.search(r'canine|dog|wildcat|tilapia|fish|aquaculture|veterinary|livestock',t): add(i,'A11',4); add(i,'A06',-1.5); add(i,'A22',-1)
            # Disease application vs fundamental mechanism.
            if re.search(r'hypertension|cardiac|cancer|diabetes|liver disease|preeclampsia|osteoarthritis',t): add(i,'A22',-0.8)
            # Optical/antenna vs semiconductor device.
            if re.search(r'photodetector|transistor|semiconductor device|flexible electronics|electronic sensor',t): add(i,'A16',3); add(i,'A17',-1)
            if re.search(r'antenna|waveguide|microwave|terahertz|metasurface|optical communication|orbital angular momentum',t): add(i,'A17',3); add(i,'A16',-0.8)
            # Material vs mechanical equipment.
            if re.search(r'polymer|composite|alloy|ceramic|coating|hydrogel|asphalt mixture|concrete material',t): add(i,'A15',2.5); add(i,'A19',-0.8)
            if re.search(r'compressor|engine|machining|manufacturing equipment|industrial equipment',t): add(i,'A19',2.8)
            # Catalytic conversion vs generic material.
            if re.search(r'co2 capture|co2 conversion|catalytic conversion|electrocatal|photocatal',t): add(i,'A21',3.2); add(i,'A15',-0.8)
            # Drug-delivery platform vs disease diagnosis/treatment outcome.
            if re.search(r'liposome|drug delivery|nanomedicine|pharmaceutical formulation|therapeutic carrier',t): add(i,'A29',3.2)
    return s

def softmax(x:np.ndarray)->np.ndarray:
    x=x-x.max(axis=1,keepdims=True); e=np.exp(np.clip(x,-40,40)); return e/(e.sum(axis=1,keepdims=True)+1e-12)

def _fit_representation(all_texts:list[str], prototypes:list[str], dim:int, seed:int):
    v=vectorizer(); X=v.fit_transform(all_texts+prototypes)
    d=min(dim,max(2,min(X.shape)-1)); svd=TruncatedSVD(n_components=d,random_state=seed,n_iter=8)
    Z=normalize(svd.fit_transform(X)); return Z[:len(all_texts)],Z[len(all_texts):],v,svd

def hybrid_predict(df:pd.DataFrame,tax_axis:dict[str,dict[str,str]],dimension:str,calibration:pd.DataFrame|None=None,seed:int=42,weights:tuple[float,float,float]=(0.34,0.46,0.20)):
    ids=list(tax_axis); prototypes=[tax_axis[x]['prototype_en'] for x in ids]
    textcol='technical_route_text' if dimension=='technical' else 'application_scenario_text'
    texts=df[textcol].tolist(); D,P,_,_=_fit_representation(texts,prototypes,56,seed)
    proto=cosine_similarity(D,P); centroid=proto.copy()
    clf_prob=np.full_like(proto,1/len(ids),dtype=float)
    if calibration is not None and len(calibration):
        label_col=f'{dimension}_cluster_id'
        cal=calibration.merge(df[['document_id']],on='document_id',how='inner')
        doc_index={d:i for i,d in enumerate(df.document_id)}; cidx=np.array([doc_index[x] for x in cal.document_id])
        y=cal[label_col].astype(str).to_numpy()
        # Centroids blend calibration examples with taxonomy prototype.
        C=[]
        for j,cid in enumerate(ids):
            ii=cidx[y==cid]
            if len(ii): C.append(normalize((.86*D[ii].mean(axis=0)+.14*P[j]).reshape(1,-1))[0])
            else: C.append(P[j])
        centroid=cosine_similarity(D,np.vstack(C))
        # Linear discriminative layer; taxonomy prototypes are added as pseudo-examples for rare classes.
        train_text=[texts[i] for i in cidx]+prototypes+[(tax_axis[c]['label_zh']+' '+tax_axis[c]['prototype_en']) for c in ids]
        train_y=list(y)+ids+ids
        vv=vectorizer(18000); X=vv.fit_transform(train_text+texts); Xtr=X[:len(train_text)]; Xall=X[len(train_text):]
        clf=SGDClassifier(loss='log_loss',max_iter=1500,tol=1e-4,class_weight='balanced',alpha=2e-5,random_state=seed)
        clf.fit(Xtr,train_y); pr=clf.predict_proba(Xall); cmap={c:i for i,c in enumerate(clf.classes_)}
        clf_prob=np.full((len(df),len(ids)),1e-8)
        for j,cid in enumerate(ids):
            if cid in cmap: clf_prob[:,j]=pr[:,cmap[cid]]
        clf_prob=clf_prob/(clf_prob.sum(axis=1,keepdims=True)+1e-12)
    rs=rule_scores(df,ids,dimension); rs=boundary_adjust(df,ids,rs,dimension); rule_prob=softmax(rs/2.3)
    a,b,c=weights
    sem=softmax((.42*proto+.58*centroid)*7.0)
    total=a*sem+b*clf_prob+c*rule_prob
    # Strong rule margin can override only when evidence is decisive.
    rr=np.argsort(-rs,axis=1); rmargin=rs[np.arange(len(df)),rr[:,0]]-rs[np.arange(len(df)),rr[:,1]]
    
    if dimension=='technical':
        strong_ids={'T03','T04','T05','T06','T07','T09','T15','T20','T21','T22','T24','T29','T30'}
    else:
        strong_ids=set(ids)
    strong=(rs[np.arange(len(df)),rr[:,0]]>=5.0)&(rmargin>=2.2)&np.array([ids[j] in strong_ids for j in rr[:,0]])
    total[strong]*=.72; total[strong,rr[strong,0]]+=.28
    # Local pairwise boundary adjudication: only activates when the two competing
    # labels are an explicitly defined confusion pair. This avoids global rule domination.
    pre_rank=np.argsort(-total,axis=1)
    idpos={x:i for i,x in enumerate(ids)}
    for i,row in df.iterrows():
        pair={ids[pre_rank[i,0]],ids[pre_rank[i,1]]}
        t=(clean(row.en_name)+' '+kw_text(row.keywords)+' '+clean(row.en_abstract)).lower()
        chosen=None
        if dimension=='technical':
            if pair=={'T12','T13'}:
                syn=bool(re.search(r'we (synthesi[sz]ed|prepared|fabricated|developed)|was synthesized|were synthesized|hydrothermal|polymeri[sz]ation|deposition|annealing|electrospinning',t))
                char=bool(re.search(r'characteri[sz]ation|characteri[sz]ed by|\bxrd\b|\bsem\b|\btem\b|raman|ftir|impedance spectroscopy|mechanical testing|direct shear test',t))
                chosen='T12' if syn else ('T13' if char else None)
            elif pair=={'T22','T08'}:
                animal=bool(re.search(r'\b(rats?|mice|murine|rabbit|beagle|canine|tilapia|zebrafish|animal model)\b',t));inter=bool(re.search(r'administer|injected|treated|supplement|induced|dose|feeding trial|in vivo',t))
                chosen='T22' if animal and inter else ('T08' if re.search(r'cell culture|primary cells|in vitro|western blot',t) else None)
            elif pair=={'T09','T24'}:
                chosen='T09' if re.search(r'rna-seq|transcriptom|proteom|metabolom|single-cell|whole-genome|next-generation sequencing',t) else ('T24' if re.search(r'\bpcr\b|qrt-pcr|qpcr|genotyp|polymorphism|gene variant',t) else None)
            elif pair=={'T17','T14'}:
                chosen='T17' if re.search(r'prototype|fabricated and measured|measurements demonstrate|device was fabricated',t) else ('T14' if re.search(r'finite element|numerical simulation|computational fluid dynamics|monte carlo',t) else None)
            elif pair=={'T03','T11'}:
                cohort=bool(re.search(r'retrospective|prospective|cross-sectional|population-based|cohort|survival|risk factors|cox regression',t));newdiag=bool(re.search(r'novel.*(diagnostic ultrasound|mri|medical imaging|diagnostic)|diagnostic accuracy|sensitivity and specificity',t))
                chosen='T03' if cohort and not newdiag else ('T11' if newdiag else None)
            elif pair=={'T07','T10'}:
                chosen='T07' if re.search(r'case report|case series|case history|report of (two|three|four|five|six|seven|eight|nine|ten) cases',t) else ('T10' if re.search(r'immunohistochem|histopatholog|histomorpholog',t) else None)
            elif pair=={'T18','T12'}:
                chosen='T18' if re.search(r'catalytic conversion|catalyst|electrocatal|photocatal|cross-coupling',t) else ('T12' if re.search(r'synthesi[sz]ed|prepared|fabricated|hydrothermal|polymeri[sz]ation',t) else None)
        else:
            if pair=={'A16','A17'}:
                chosen='A16' if re.search(r'photodetector|transistor|semiconductor device|flexible electronics|electronic sensor',t) else ('A17' if re.search(r'antenna|waveguide|microwave|terahertz|metasurface|optical communication',t) else None)
            elif pair=={'A15','A21'}:
                chosen='A21' if re.search(r'co2 capture|co2 conversion|catalytic conversion|electrocatal|photocatal',t) else 'A15'
            elif pair=={'A03','A29'}:
                chosen='A29' if re.search(r'liposome|drug delivery|nanomedicine|pharmaceutical formulation|therapeutic carrier',t) else 'A03'
            elif pair=={'A11','A12'}:
                chosen='A11' if re.search(r'canine|dog|wildcat|tilapia|fish|aquaculture|veterinary|livestock',t) else ('A12' if re.search(r'ecology|biodiversity|conservation|forest|wildlife|crop|agriculture',t) else None)
        if chosen in idpos:
            total[i]*=.88; total[i,idpos[chosen]]+=.12
    rank=np.argsort(-total,axis=1); top=rank[:,0]; sec=rank[:,1]
    margin=total[np.arange(len(df)),top]-total[np.arange(len(df)),sec]
    conf=np.clip(.40+.45*total[np.arange(len(df)),top]+1.3*margin,0,.99)
    return {'primary':[ids[i] for i in top],'secondary':[ids[i] for i in sec],'confidence':conf,'scores':total,'rule_scores':rs,'semantic_prob':sem,'classifier_prob':clf_prob,'rule_prob':rule_prob,'strong_rule':strong,'rule_rank':rr,'ids':ids,'margin':margin,'top_rule_id':[ids[i] for i in rr[:,0]],'top_rule_score':rs[np.arange(len(df)),rr[:,0]],'rule_margin':rmargin}

def run(cfg:Config):
    out=Path(cfg.output_dir); out.mkdir(parents=True,exist_ok=True)
    df=load(cfg.input_file); tax=json.loads(Path(cfg.taxonomy_file).read_text(encoding='utf-8'))
    cal=pd.read_csv(cfg.calibration_file) if cfg.calibration_file else None
    tg=hybrid_predict(df,tax['technical'],'technical',cal,cfg.random_state,weights=(0.30,0.45,0.25))
    ag=hybrid_predict(df,tax['application'],'application',cal,cfg.random_state,weights=(0.20,0.60,0.20))
    res=df[['document_id','en_name','en_abstract','keywords','technical_route_text','application_scenario_text']].copy()
    for kind,g in [('technical',tg),('application',ag)]:
        res[f'{kind}_cluster_id']=g['primary'];res[f'{kind}_secondary_id']=g['secondary'];res[f'{kind}_confidence']=np.round(g['confidence'],4);res[f'{kind}_decision_margin']=np.round(g['margin'],4);res[f'{kind}_needs_review']=(g['margin']<0.055)|(g['confidence']<0.58);res[f'{kind}_top_rule_id']=g['top_rule_id'];res[f'{kind}_top_rule_score']=np.round(g['top_rule_score'],3)
        res[f'{kind}_label_zh']=res[f'{kind}_cluster_id'].map(lambda x:tax[kind][x]['label_zh'])
    res.to_csv(out/'dual_cluster_results_v6.csv',index=False,encoding='utf-8-sig')
    res.to_json(out/'dual_cluster_results_v6.json',orient='records',force_ascii=False,indent=2)
    meta={'documents':len(res),'mode':'hybrid_semisupervised_boundary_rules','calibration_file':cfg.calibration_file,'random_state':cfg.random_state}
    (out/'run_metadata_v6.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return res,meta
