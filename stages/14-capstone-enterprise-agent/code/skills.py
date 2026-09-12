"""Discover summaries first; load one trusted procedure only when it is needed."""
from __future__ import annotations
import json
from pathlib import Path
from domain import DATA, BoundaryError


class SkillLibrary:
    def __init__(self, root: Path = DATA / 'skills'):
        self.root = root
        self.manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))

    def discover(self) -> list[dict]:
        return [{'name':k,'description':v['description']} for k,v in self.manifest.items()]

    def load(self, name: str, language: str) -> str:
        if name not in self.manifest or language not in {'zh','en'}:
            raise BoundaryError('unknown_skill')
        path=(self.root/self.manifest[name]['file']).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise BoundaryError('invalid_skill_path')
        content=path.read_text(encoding='utf-8')
        marker=f'## {language}\n'
        body=content.split(marker,1)[1].split('\n## ',1)[0].strip()
        if len(body)>6000: raise BoundaryError('skill_too_large')
        return body
