import argparse
from topicfusion_v7 import Config, run
p=argparse.ArgumentParser(description='TopicFusion v7 bilingual technical-route/application-scenario clustering')
p.add_argument('--input',required=True)
p.add_argument('--output',default='results_v7')
p.add_argument('--calibration')
p.add_argument('--taxonomy')
p.add_argument('--rules')
p.add_argument('--seed',type=int,default=42)
a=p.parse_args()
print(run(Config(a.input,a.output,a.calibration,a.taxonomy,a.rules,a.seed)))
