#!/usr/bin/env python3
"""Refresh local guide bytes atomically without hydrating old Desktop placeholders."""
from pathlib import Path
import sys
src=Path(sys.argv[1]);dest=Path(sys.argv[2]);count=0
for p in sorted(src.rglob('*')):
 if not p.is_file() or p.is_symlink() or p.suffix=='.pdf':continue
 if p.stat().st_flags&0x40000000:raise RuntimeError('Source is iCloud-only: '+str(p))
 target=dest/p.relative_to(src);target.parent.mkdir(parents=True,exist_ok=True)
 temp=target.with_name(target.name+'.incoming');temp.write_bytes(p.read_bytes());temp.replace(target);count+=1
print('Refreshed',count,'guide files')
