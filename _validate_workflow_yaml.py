from pathlib import Path
import yaml
path = Path('/mnt/c/Users/Makin/Desktop/Proton build/proton-arm64-nightlies/.github/workflows/proton-nightly-build.yml')
obj = yaml.safe_load(path.read_text(encoding='utf-8'))
on_key = 'on' if 'on' in obj else True
print('loaded:', type(obj).__name__)
print('jobs:', list(obj.get('jobs', {}).keys()))
print('dispatch_inputs:', list(obj[on_key]['workflow_dispatch']['inputs'].keys()))
