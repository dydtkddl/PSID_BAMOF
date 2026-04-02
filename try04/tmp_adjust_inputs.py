#!/usr/bin/env python3
from pathlib import Path

pairs = [
    Path(r'/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/input.inp'),
    Path(r'/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate/input.inp'),
]

for f in pairs:
    if not f.exists():
        print(f'MISSING: {f}')
        continue
    text = f.read_text()
    text = text.replace('MAX_SCF 200', 'MAX_SCF 300', 1)
    text = text.replace('ALPHA 0.15', 'ALPHA 0.05', 1)
    text = text.replace('ALPHA 0.05\n', 'ALPHA 0.05\n        NBUFFER 8\n', 1)

    if '&OUTER_SCF' not in text:
        anchor = '    &PRINT\n      &RESTART ON'
        
        insert = '    &OUTER_SCF T\n      MAX_SCF 10\n      EPS_SCF 5.0E-7\n    &END OUTER_SCF\n\n'
        text = text.replace(anchor, insert + anchor, 1)

    f.write_text(text)
    print(f'updated: {f}')

for f in pairs:
    if f.exists():
        lines = []
        for L in f.read_text().splitlines():
            if any(k in L for k in ('MAX_SCF', 'ALPHA', 'NBUFFER', '&OUTER_SCF')):
                lines.append(L)
        print(f'--- {f} ---')
        print('\n'.join(lines[:20]))
