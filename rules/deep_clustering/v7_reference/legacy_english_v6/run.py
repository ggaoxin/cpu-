import argparse
from topicfusion_v6 import Config,run
p=argparse.ArgumentParser()
p.add_argument('--input',required=True);p.add_argument('--taxonomy',default='taxonomy_v6.json');p.add_argument('--output',default='results');p.add_argument('--calibration');p.add_argument('--seed',type=int,default=42)
a=p.parse_args();run(Config(a.input,a.taxonomy,a.output,a.calibration,a.seed))
