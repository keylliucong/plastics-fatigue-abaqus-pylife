#!/usr/bin/env python3
"""Preview or synchronize the theory guide after detecting changes on both sides."""
import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path
VAULT=Path(__file__).resolve().parent.parent
REPO=Path('/Users/liucong/Documents/ChatGPT/结构设计/plastics-fatigue-abaqus-pylife')
NAME='项目理论知识与阅读指南.md'
def digest(b): return hashlib.sha256(b).hexdigest()
def decide(a,b,base):
 if a==b:return 'equal'
 if base and a!=base and b==base:return 'to_repo'
 if base and b!=base and a==base:return 'to_vault'
 return 'conflict'
def write_atomic(path,content):
 with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f: tmp=f.name;f.write(content)
 try:os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');args=p.parse_args()
 vault=VAULT/'项目资料'/NAME;repo=REPO/'docs/research'/NAME;state=VAULT/'工具/guide-sync-state.json'
 a=vault.read_bytes();b=repo.read_bytes();base=json.loads(state.read_text())['sha256'] if state.exists() else None
 action=decide(digest(a),digest(b),base)
 print({'equal':'两侧内容一致','to_repo':'知识库有新修改，项目仓库未变','to_vault':'项目仓库有新修改，知识库未变','conflict':'两侧均有修改或缺少一致基线；请人工比较'}[action])
 if action=='conflict':return 2
 if not args.apply:
  print('预览：未修改文件。使用 --apply 执行同步。');return 0
 if action=='to_repo':write_atomic(repo,a);b=a
 elif action=='to_vault':write_atomic(vault,b);a=b
 write_atomic(state,(json.dumps({'sha256':digest(a)},ensure_ascii=False,indent=2)+'\n').encode())
 print('同步基线已更新；不会自动提交或推送 Git。');return 0
if __name__=='__main__':
 try:sys.exit(main())
 except (OSError,ValueError,KeyError) as exc:print('同步失败：'+str(exc),file=sys.stderr);sys.exit(1)
