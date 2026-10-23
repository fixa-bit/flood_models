"""Run preparation sequentially with durable progress and per-stage logs."""
import json
import os
import subprocess
import sys
from pathlib import Path
from common import setup,load,write_json,now


def run(args):
    cfg,data=load(args)
    root=Path(__file__).resolve().parents[1]
    logs=data / 'processed' / cfg['area']['name'] / 'validation_reports'
    logs.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    scratch=root / '.tmp'; scratch.mkdir(exist_ok=True)
    env['TEMP']=env['TMP']=str(scratch)
    progress={'pilot':cfg['area']['name'],'started_at':now(),'status':'RUNNING','completed_stages':[]}
    status_path=logs/'pipeline_status.json'
    if args.resume and status_path.exists():
        previous=json.loads(status_path.read_text(encoding='utf-8'))
        if previous['pilot']!=cfg['area']['name']:
            raise ValueError('Progress belongs to another pilot')
        progress['completed_stages']=[s for s in previous.get('completed_stages',[]) if s['exit_code']==0]
        progress['resumed_at']=now()
    stages=[('preprocess',[sys.executable,'scripts/preprocess.py']),
            ('tests',[sys.executable,'-m','pytest','-q']),
            ('verify_sources',[sys.executable,'scripts/verify_sources.py','--skip-osm']),
            ('audit',[sys.executable,'scripts/audit.py'])]
    for name,command in stages:
        if any(s['stage']==name for s in progress['completed_stages']):
            print(f'Reusing completed stage {name}',flush=True)
            continue
        progress['current_stage']=name
        write_json(status_path,progress)
        if name!='tests':
            command+=['--config',str(Path(args.config).resolve()),'--root',cfg['_root']]
        print(f'{now()} starting {name}',flush=True)
        with (logs/f'{name}.log').open('w',encoding='utf-8') as stream:
            result=subprocess.run(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
        progress['completed_stages'].append({'stage':name,'exit_code':result.returncode,'finished_at':now()})
        if result.returncode:
            progress.update(status='FAILED',finished_at=now())
            write_json(status_path,progress)
            raise SystemExit(result.returncode)
    progress.update(status='COMPLETED',finished_at=now(),current_stage=None)
    write_json(status_path,progress)
    print(json.dumps(progress,indent=2),flush=True)


if __name__=='__main__':
    parser=setup(__doc__)
    parser.add_argument('--resume',action='store_true',help='Resume after successfully completed stages in this pilot')
    run(parser.parse_args())
