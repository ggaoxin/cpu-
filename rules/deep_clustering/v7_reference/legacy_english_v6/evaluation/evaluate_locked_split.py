from pathlib import Path
import sys,json
import numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,f1_score,adjusted_rand_score,normalized_mutual_info_score,homogeneity_completeness_v_measure
sys.path.insert(0,'/mnt/data/TopicFusion-multifield-v6')
from topicfusion_v6.pipeline import load,hybrid_predict
ROOT=Path('/mnt/data/TopicFusion-multifield-v6/evaluation');ROOT.mkdir(exist_ok=True)
DATA='/mnt/data/35243bd3-34f2-4b2a-b0b0-884c5552143f.json'
TAX=json.load(open('/mnt/data/TopicFusion-multifield-v6/taxonomy_v6.json',encoding='utf-8'))
G=pd.read_csv('/mnt/data/topicfusion_new_experiment/gold_high_confidence_498.csv')
D=load(DATA);V5=pd.read_csv('/mnt/data/TopicFusion-multifield-v5/results/dual_cluster_results_v5.csv')
def split(df,label,seed=20260802):
 rng=np.random.default_rng(seed);tr=[];dv=[];te=[]
 for _,g in df.groupby(label):
  ids=g.index.to_numpy().copy();rng.shuffle(ids);n=len(ids)
  if n==1: tr+=ids.tolist()
  elif n==2: tr+=ids[:1].tolist();te+=ids[1:].tolist()
  elif n==3: tr+=ids[:1].tolist();dv+=ids[1:2].tolist();te+=ids[2:].tolist()
  elif n==4: tr+=ids[:2].tolist();dv+=ids[2:3].tolist();te+=ids[3:].tolist()
  else:
   ne=max(1,round(.2*n));nd=max(1,round(.2*n)); nt=n-ne-nd
   if nt<2:nt=n-2;nd=1;ne=1
   tr+=ids[:nt].tolist();dv+=ids[nt:nt+nd].tolist();te+=ids[nt+nd:].tolist()
 return np.array(sorted(tr)),np.array(sorted(dv)),np.array(sorted(te))
def metrics(y,p):
 h,c,v=homogeneity_completeness_v_measure(y,p)
 return {'n':len(y),'accuracy':float(accuracy_score(y,p)),'macro_f1':float(f1_score(y,p,average='macro',zero_division=0)),'ARI':float(adjusted_rand_score(y,p)),'NMI':float(normalized_mutual_info_score(y,p)),'V_measure':float(v),'homogeneity':float(h),'completeness':float(c)}
def combine(comp,w,use_rules=True):
 a,b,c=w;total=a*comp['semantic_prob']+b*comp['classifier_prob']+(c*comp['rule_prob'] if use_rules else 0)
 if not use_rules: total=total/(a+b)
 if use_rules:
  strong=comp['strong_rule'];rr=comp['rule_rank'];total[strong]*=.72;total[strong,rr[strong,0]]+=.28
 idx=np.argmax(total,axis=1);return np.array([comp['ids'][i] for i in idx]),total
weights=[(.20,.60,.20),(.25,.55,.20),(.30,.50,.20),(.35,.45,.20),(.25,.60,.15),(.30,.55,.15),(.35,.50,.15),(.25,.50,.25),(.30,.45,.25)]
summary={}
for dim in ['technical','application']:
 label=f'{dim}_cluster_id';tr,dv,te=split(G,label)
 cal=G.iloc[tr][['document_id','technical_cluster_id','application_cluster_id']]
 comp=hybrid_predict(D,TAX[dim],dim,calibration=cal,seed=20260802,weights=(.3,.5,.2))
 docpos={d:i for i,d in enumerate(D.document_id)}; devpos=np.array([docpos[x] for x in G.iloc[dv].document_id]);testpos=np.array([docpos[x] for x in G.iloc[te].document_id])
 yd=G.iloc[dv][label].astype(str).to_numpy();yt=G.iloc[te][label].astype(str).to_numpy()
 dev=[]
 for w in weights:
  p,_=combine(comp,w,True);m=metrics(yd,p[devpos]);dev.append({'weights':w,**m})
 best=max(dev,key=lambda x:(x['macro_f1'],x['accuracy'],x['NMI']));w=tuple(best['weights'])
 pfull,total=combine(comp,w,True);pred=pfull[testpos]
 predred,_=combine(comp,(w[0]/(w[0]+w[1]),w[1]/(w[0]+w[1]),0),False);predred=predred[testpos]
 v5map=dict(zip(V5.document_id,V5[label]));p5=G.iloc[te].document_id.map(v5map).astype(str).to_numpy()
 test=G.iloc[te][['document_id','en_name',label]].copy();test['v5_prediction']=p5;test['v6_reduced_prediction']=predred;test['v6_prediction']=pred;test['v6_correct']=test[label].astype(str).eq(pred)
 test.to_csv(ROOT/f'{dim}_locked_test_predictions_v6.csv',index=False,encoding='utf-8-sig')
 summary[dim]={'split':{'train':len(tr),'dev':len(dv),'test':len(te)},'selected_weights':w,'dev_best':best,'v5_baseline':metrics(yt,p5),'v6_reduced_rule':metrics(yt,predred),'v6_full':metrics(yt,pred)}
 pd.DataFrame(dev).to_csv(ROOT/f'{dim}_dev_weight_search.csv',index=False,encoding='utf-8-sig')
(ROOT/'locked_test_metrics_v6.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[]
for dim,d in summary.items():
 for model in ['v5_baseline','v6_reduced_rule','v6_full']:rows.append({'dimension':dim,'model':model,**d[model]})
pd.DataFrame(rows).to_csv(ROOT/'locked_test_metrics_v6.csv',index=False,encoding='utf-8-sig')
print(json.dumps(summary,ensure_ascii=False,indent=2))
