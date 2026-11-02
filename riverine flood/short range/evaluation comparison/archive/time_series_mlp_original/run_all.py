"""Run the frozen single-seed experiments sequentially on CPU."""
import hashlib
import json
import time
from pathlib import Path

from time_series_mlp.train import train_config


def main():
    root = Path(__file__).resolve().parents[1]
    shared = root / 'time_series_mlp'
    protocol = json.loads((shared / 'experiment_protocol.json').read_text())
    for path, digest in protocol['config_hashes'].items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            raise ValueError('A frozen configuration changed before training')
    configs = ['nhits/config.yaml', 'nbeatsx/config.yaml', 'nhits/config_lstm_control.yaml']
    state = {'status': 'running', 'completed': {}, 'configs': configs}
    started = time.perf_counter()
    for relative in configs:
        state['active_config'] = relative
        (shared / 'training_status.json').write_text(json.dumps(state, indent=2) + '\n')
        state['completed'][relative] = train_config(root / relative)
    state.update(status='complete', elapsed_seconds=time.perf_counter() - started)
    state.pop('active_config', None)
    (shared / 'training_status.json').write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
