from __future__ import annotations
import sys, json, math, hashlib, shutil, zipfile
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score,f1_score,adjusted_rand_score,normalized_mutual_info_score,homogeneity_completeness_v_measure
sys.path.insert(0,'/mnt/data')
import build_topicfusion_v7_unified as b
ROOT=b.ROOT

def metrics(y,p):
    h,c,v=homogeneity_completeness_v_measure(y,p)
    return {'n':len(y),'accuracy':accuracy_score(y,p),'macro_f1':f1_score(y,p,average='macro',zero_division=0),'ARI':adjusted_rand_score(y,p),'NMI':normalized_mutual_info_score(y,p),'V_measure':v,'homogeneity':h,'completeness':c}

def split_strat(g,label,seed=20260802):
    rng=np.random.default_rng(seed);tr=[];dv=[];te=[]
    for _,x in g.groupby(label):
        ix=x.index.to_numpy().copy();rng.shuffle(ix);n=len(ix)
        if n==1: tr+=ix.tolist()
        elif n==2: tr+=ix[:1].tolist();te+=ix[1:].tolist()
        elif n==3: tr+=ix[:1].tolist();dv+=ix[1:2].tolist();te+=ix[2:].tolist()
        else:
            nt=max(1,int(round(n*.60)));nd=max(1,int(round(n*.20)));nt=min(nt,n-2);nd=min(nd,n-nt-1)
            tr+=ix[:nt].tolist();dv+=ix[nt:nt+nd].tolist();te+=ix[nt+nd:].tolist()
    return np.array(sorted(tr)),np.array(sorted(dv)),np.array(sorted(te))

def prepare(d,tax,axis,cal,seed=20260802):
    textcol='technical_route_text' if axis=='technical' else 'application_scenario_text'
    texts=d[textcol].tolist(); ids=list(tax);protos=[tax[c]['label_zh']+' '+tax[c]['prototype_zh'] for c in ids]
    vec=TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=1,max_features=45000,sublinear_tf=True)
    X=vec.fit_transform(texts+protos)
    nc=min(90,max(2,X.shape[0]-1),max(2,X.shape[1]-1));svd=TruncatedSVD(n_components=nc,random_state=seed);Z=normalize(svd.fit_transform(X));D=Z[:len(d)];P=Z[len(d):]
    proto=cosine_similarity(D,P);centers=P.copy();clfprob=np.full((len(d),len(ids)),1/len(ids))
    if cal is not None and len(cal):
        pos={x:i for i,x in enumerate(d.document_id)};idx=np.array([pos[x] for x in cal.document_id]);y=cal[f'{axis}_cluster_id'].astype(str).to_numpy();C=[]
        for j,c in enumerate(ids):
            ii=idx[y==c];C.append(normalize((.9*D[ii].mean(axis=0)+.1*P[j]).reshape(1,-1))[0] if len(ii) else P[j])
        centers=np.vstack(C)
        anchors=protos;train=[texts[i] for i in idx]+anchors+anchors;yy=list(y)+ids+ids
        vv=TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=1,max_features=45000,sublinear_tf=True);Q=vv.fit_transform(train+texts)
        clf=SGDClassifier(loss='log_loss',max_iter=1800,tol=1e-4,class_weight='balanced',alpha=1e-5,random_state=seed)
        clf.fit(Q[:len(train)],yy);pr=clf.predict_proba(Q[len(train):]);cmap={c:i for i,c in enumerate(clf.classes_)};clfprob=np.full((len(d),len(ids)),1e-9)
        for j,c in enumerate(ids):
            if c in cmap:clfprob[:,j]=pr[:,cmap[c]]
        clfprob/=clfprob.sum(axis=1,keepdims=True)
    cent=cosine_similarity(D,centers);semraw=.35*proto+.65*cent;sem=np.exp(7*(semraw-semraw.max(axis=1,keepdims=True)));sem/=sem.sum(axis=1,keepdims=True)
    rules=b.TECH_RULES_MODEL if axis=='technical' else b.APP_RULES_MODEL;rs=np.zeros((len(d),len(ids)));idp={c:j for j,c in enumerate(ids)}
    for i,r in d.iterrows():
        sc,_=b.phrase_scores(r.ch_name,r.ch_abstract,r.keywords,rules)
        for c,v in sc.items():rs[i,idp[c]]=v
    rp=np.exp((rs-rs.max(axis=1,keepdims=True))/2.7);rp/=rp.sum(axis=1,keepdims=True)
    return {'ids':ids,'sem':sem,'clf':clfprob,'rule':rp}

def predict_from(comp,d,axis,w,boundary):
    a,c,r=w;total=a*comp['sem']+c*comp['clf']+r*comp['rule'];rank=np.argsort(-total,axis=1);ids=comp['ids'];pred=np.array([ids[j] for j in rank[:,0]],object);sec=np.array([ids[j] for j in rank[:,1]],object)
    if boundary: pred=b.boundary_adjust(d,axis,pred,total,ids)
    for i,p in enumerate(pred):
        for j in rank[i]:
            if ids[j]!=p:sec[i]=ids[j];break
    vals=np.sort(total,axis=1);margin=vals[:,-1]-vals[:,-2];topv=vals[:,-1]
    out=pd.DataFrame({f'{axis}_cluster_id':pred,f'{axis}_secondary_id':sec,f'{axis}_confidence':np.round(np.clip(.40+.42*topv+1.2*margin,.4,.99),4),f'{axis}_decision_margin':np.round(margin,4)})
    out[f'{axis}_needs_review']=(margin<.045)|(out[f'{axis}_confidence']<.60)
    return out

def main():
    d=b.load_data();gp=ROOT/'gold'/'gold_zh_model_reviewed_round3_1000.csv';g=pd.read_csv(gp);g['keywords']=g.keywords.map(b.kw_list)
    # Dimension-specific trustworthy subsets.
    g['technical_gold_quality']=np.where(g.technical_confidence>=.75,'high',np.where(g.technical_confidence>=.60,'medium','needs_review'))
    g['application_gold_quality']=np.where(g.application_confidence>=.80,'high',np.where(g.application_confidence>=.65,'medium','needs_review'))
    g['gold_quality']=np.where((g.technical_gold_quality=='high')&(g.application_gold_quality=='high'),'high',np.where((g.technical_gold_quality!='needs_review')&(g.application_gold_quality!='needs_review'),'medium','needs_review'))
    g.to_csv(gp,index=False,encoding='utf-8-sig');g.to_json(ROOT/'gold'/'gold_zh_model_reviewed_round3_1000.json',orient='records',force_ascii=False,indent=2)
    for axis in ['technical','application']:
        for q in ['high','medium','needs_review']:
            g[g[f'{axis}_gold_quality']==q].to_csv(ROOT/'gold'/f'gold_zh_{axis}_{q}.csv',index=False,encoding='utf-8-sig')
    for q in ['high','medium','needs_review']:
        g[g.gold_quality==q].to_csv(ROOT/'gold'/f'gold_zh_combined_{q}.csv',index=False,encoding='utf-8-sig')
    evalrows=[];production=[];devrows=[]
    grids=[(.55,.45,0),(.40,.45,.15),(.35,.45,.20),(.30,.45,.25),(.30,.40,.30),(.25,.45,.30)]
    for axis,tax in [('technical',b.TECH),('application',b.APP)]:
        label=f'{axis}_cluster_id';high=g[g[f'{axis}_gold_quality']=='high'].reset_index(drop=True);tr,dv,te=split_strat(high,label)
        cal=high.iloc[tr][['document_id','technical_cluster_id','application_cluster_id']].copy();dev=high.iloc[dv].copy();test=high.iloc[te].copy()
        cal.to_csv(ROOT/'evaluation'/f'{axis}_calibration_gold.csv',index=False,encoding='utf-8-sig');dev.to_csv(ROOT/'evaluation'/f'{axis}_development_gold.csv',index=False,encoding='utf-8-sig');test.to_csv(ROOT/'evaluation'/f'{axis}_locked_test_gold.csv',index=False,encoding='utf-8-sig')
        comp=prepare(d,tax,axis,cal);pos={x:i for i,x in enumerate(d.document_id)};devpos=np.array([pos[x] for x in dev.document_id]);testpos=np.array([pos[x] for x in test.document_id]);yd=dev[label].astype(str).to_numpy();yt=test[label].astype(str).to_numpy()
        best=None
        for w in grids:
            p=predict_from(comp,d,axis,w,boundary=(w[2]>0));m=metrics(yd,p.iloc[devpos][label].astype(str).to_numpy());score=.55*m['macro_f1']+.25*m['accuracy']+.20*m['NMI'];devrows.append({'dimension':axis,'weights':str(w),'score':score,**m})
            if best is None or score>best[0]:best=(score,w,m)
        base=predict_from(comp,d,axis,(.55,.45,0),False);full=predict_from(comp,d,axis,best[1],True)
        for model,pdf,w in [('v6_architecture_no_zh_rules',base,(.55,.45,0)),('v7_unified_with_zh_rules',full,best[1])]:
            m=metrics(yt,pdf.iloc[testpos][label].astype(str).to_numpy());m.update({'dimension':axis,'model':model,'train_n':len(tr),'dev_n':len(dv),'locked_test_n':len(te),'weights':str(w)});evalrows.append(m)
        out=test[['document_id','ch_name',label]].copy();out[f'{axis}_baseline_prediction']=base.iloc[testpos][label].to_numpy();out[f'{axis}_v7_prediction']=full.iloc[testpos][label].to_numpy();out['baseline_correct']=out[label].eq(out[f'{axis}_baseline_prediction']);out['v7_correct']=out[label].eq(out[f'{axis}_v7_prediction']);out.to_csv(ROOT/'evaluation'/f'{axis}_locked_test_predictions.csv',index=False,encoding='utf-8-sig')
        out[out[label]!=out[f'{axis}_v7_prediction']].groupby([label,f'{axis}_v7_prediction']).size().reset_index(name='count').sort_values('count',ascending=False).to_csv(ROOT/'evaluation'/f'{axis}_confusion_pairs_v7.csv',index=False,encoding='utf-8-sig')
        # Production model with all dimension-specific high Gold and selected weights.
        allhigh=g[g[f'{axis}_gold_quality']=='high'][['document_id','technical_cluster_id','application_cluster_id']]
        comp2=prepare(d,tax,axis,allhigh);prod=predict_from(comp2,d,axis,best[1],True);production.append(prod)
    pd.DataFrame(devrows).to_csv(ROOT/'evaluation'/'development_weight_search.csv',index=False,encoding='utf-8-sig');mdf=pd.DataFrame(evalrows);mdf.to_csv(ROOT/'evaluation'/'locked_test_metrics_v7.csv',index=False,encoding='utf-8-sig');mdf.to_json(ROOT/'evaluation'/'locked_test_metrics_v7.json',orient='records',force_ascii=False,indent=2)
    res=pd.concat([d[['document_id','ch_name','ch_abstract','keywords','technical_route_text','application_scenario_text']],production[0],production[1]],axis=1);res['technical_label_zh']=res.technical_cluster_id.map(lambda x:b.TECH[x]['label_zh']);res['application_label_zh']=res.application_cluster_id.map(lambda x:b.APP[x]['label_zh']);res.to_csv(ROOT/'results'/'dual_cluster_results_v7_zh_1000.csv',index=False,encoding='utf-8-sig');res.to_json(ROOT/'results'/'dual_cluster_results_v7_zh_1000.json',orient='records',force_ascii=False,indent=2)
    # Update report.
    counts={'documents':len(d),'missing_title':int(d.ch_name.eq('').sum()),'missing_abstract':int(d.ch_abstract.eq('').sum()),'missing_keywords':int(d.keywords.map(len).eq(0).sum()),'technical_high':int((g.technical_gold_quality=='high').sum()),'application_high':int((g.application_gold_quality=='high').sum()),'combined_high':int((g.gold_quality=='high').sum()),'combined_medium':int((g.gold_quality=='medium').sum()),'combined_review':int((g.gold_quality=='needs_review').sum())}
    report=f'''# TopicFusion v7 中英文统一深度聚类复现报告\n\n## 1. 中英文统一ID\n\n英文 v6 的技术路线 `T01–T33` 和应用场景 `A01–A30` 全部原样保留。中文新增方法从 `T34` 开始，中文新增场景从 `A31` 开始。不存在删除英文类别或用中文含义覆盖英文ID的情况。\n\n- v7技术路线总数：{len(b.TECH)}（英文v6保留33，中文新增{len(b.NEW_TECH)}）\n- v7应用场景总数：{len(b.APP)}（英文v6保留30，中文新增{len(b.NEW_APP)}）\n\n## 2. 数据核验\n\n- 中文文献：{counts['documents']}篇\n- 缺标题：{counts['missing_title']}篇\n- 缺摘要：{counts['missing_abstract']}篇\n- 缺关键词：{counts['missing_keywords']}篇\n\n## 3. Gold三轮复核\n\n1. 标题、关键词、摘要分字段证据打分；\n2. 按核心贡献执行任务优先和研究设计优先的边界裁决；\n3. 语义原型交叉检查，证据不足或冲突样本降级为待复核。\n\n由于技术路线和应用场景证据强度不同，分别建立可信集：\n\n- 技术路线高可信Gold：{counts['technical_high']}篇\n- 应用场景高可信Gold：{counts['application_high']}篇\n- 两个维度同时高可信：{counts['combined_high']}篇\n- 两维中可信：{counts['combined_medium']}篇\n- 至少一个维度待人工复核：{counts['combined_review']}篇\n\n该Gold是三轮模型复核Gold，不等同于跨学科专家逐篇人工金标准。\n\n## 4. 锁定测试指标\n\n训练、开发和锁定测试按类别分层。权重只在开发集选择，锁定测试不参与规则设计。\n\n{mdf[['dimension','model','n','accuracy','macro_f1','ARI','NMI','V_measure','train_n','dev_n','locked_test_n','weights']].to_markdown(index=False)}\n\n## 5. 规则库优化原则\n\n- 深度模型与任务类型冲突时，预测、故障诊断、聚类识别等任务优先作为主技术路线。\n- 确定性优化、随机鲁棒优化和多主体博弈分别建类。\n- 空间格局分析与面板计量回归分开；综合评价与耦合协调分开。\n- 配电网、新能源发电、储能、电力电子、设备运维、高压直流分别建应用场景边界。\n- 英文规则继续保存在 `legacy_english_v6`，中文规则和共享边界位于 `rules`。\n\n## 6. 混合语言支持边界\n\n当前离线v7通过双语类别原型和共享ID实现中英文类别级统一聚类。真正的中英文原始向量联合子聚类，建议在部署时接入BGE-M3或multilingual-e5等多语言向量模型；不接入时，中文和英文分别编码后仍输出统一类别ID。\n'''
    (ROOT/'V7_UNIFIED_REPRODUCTION_REPORT.md').write_text(report,encoding='utf-8')
    # executable, hashes, zip
    shutil.copy2(Path(__file__),ROOT/'topicfusion_v7'/'finalize_and_evaluate.py');(ROOT/'requirements.txt').write_text('numpy\npandas\nscikit-learn\n',encoding='utf-8')
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt'];lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT)) for p in sorted(files)];(ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines),encoding='utf-8')
    zp=Path('/mnt/data/TopicFusion-multifield-v7-unified_delivery.zip')
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob('*'):
            if p.is_file():z.write(p,Path(ROOT.name)/p.relative_to(ROOT))
    print(json.dumps({'counts':counts,'metrics':evalrows,'zip':str(zp)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
