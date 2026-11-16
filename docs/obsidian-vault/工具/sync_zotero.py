#!/usr/bin/env python3
"""Read Zotero project collections; replace only the generated index."""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT='JV64VS9S'
VAULT=Path(__file__).resolve().parent.parent

def query(*args):
 p=subprocess.run(['zotero-cli','--json',*args],capture_output=True,text=True,check=False)
 try: data=json.loads(p.stdout)
 except json.JSONDecodeError: raise RuntimeError('Zotero CLI 返回了无法解析的响应')
 if p.returncode or not data.get('ok'): raise RuntimeError(str(data.get('error','Zotero 查询失败')))
 return data['data']

def render_index(rows,notes):
 unique={}
 for item in rows:
  key=item.get('key','')
  if item.get('itemType') not in ('note','attachment','annotation') and key: unique[key]=item
 lines=['# Zotero 项目文献实时索引','','> 由工具生成；手动修改会在下次更新时被替换。阅读笔记不会被覆盖。','','来源：Zotero 项目分类及所有子分类；按条目键去重。预览时新条目显示为普通文字；执行更新后会创建缺失的阅读笔记。','','返回 [[项目主页]]。','',f'共 {len(unique)} 条。','']
 for key,item in sorted(unique.items(),key=lambda kv:(kv[1].get('title') or '').casefold()):
  title=(item.get('title') or '未命名').replace('\n',' ').replace('|','｜').replace(']','）').replace('[','（')
  target=notes.get(key,key) if isinstance(notes,dict) else key
  label=f'[[{target}|{title}]]' if key in notes else f'{title}（{key}；尚无本地笔记）'
  doi=item.get('doi') or ''
  lines.append('- '+label+(f' — [DOI](https://doi.org/{doi})' if doi else ''))
 return '\n'.join(lines)+'\n'

def note_map(folder):
 keys={}
 for p in folder.glob('*.md'):
  text=p.read_text(encoding='utf-8')
  match=re.search(r'^zotero_key:\s*["\']?([A-Z0-9]{8})["\']?\s*$',text,re.M)
  if match: keys[match.group(1)]='文献笔记/'+p.stem
  elif re.fullmatch(r'[A-Z0-9]{8}',p.stem):keys[p.stem]='文献笔记/'+p.stem
 return keys

def readable_filename(title,key,folder):
 name=re.sub(r'[\\/:*?"<>|]',' - ',title)
 name=re.sub(r'\s+',' ',name).strip(' .')[:95].strip() or '未命名'
 candidate=folder/(name+'.md')
 return candidate if not candidate.exists() else folder/(name+' — '+key+'.md')

def create_missing_notes(rows,folder):
 created=set(); existing=note_map(folder)
 for item in rows:
  key=item.get('key','')
  if item.get('itemType') in ('note','attachment','annotation') or not re.fullmatch(r'[A-Z0-9]{8}',key): continue
  if key in existing: continue
  title=(item.get('title') or '未命名').replace('\n',' ')
  doi=item.get('doi') or '';url=item.get('url') or ''
  content=('---\n类型: 文献笔记\nzotero_key: '+json.dumps(key)+'\ndoi: '+json.dumps(doi,ensure_ascii=False)+'\naliases:\n  - '+json.dumps(key)+'\n阅读状态: 待读\n---\n\n# '+title+'\n\n- DOI：'+(f'https://doi.org/{doi}' if doi else '未提供')+'\n- 来源：'+(url or '未提供')+'\n- [在 Zotero 中打开](zotero://select/library/items/'+key+')\n\n## 问题与材料\n\n## 方法与关键结果\n\n## 条件与适用边界\n\n## 对项目的启示\n\n## 来源与待核查\n')
  try:
   with readable_filename(title,key,folder).open('x',encoding='utf-8') as f:f.write(content)
   created.add(key); existing[key]=True
  except FileExistsError:pass
 return created

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true',help='写入自动生成索引；缺省仅预览');args=parser.parse_args()
 collections=query('get','collections')['collections']; keys={ROOT}; pending=True
 while pending:
  old=len(keys); keys.update(c['key'] for c in collections if c.get('parentCollection') in keys); pending=len(keys)>old
 rows=[]
 for key in sorted(keys):
  offset=0
  while True:
   data=query('get','collection-items',key,'--limit','100','--offset',str(offset)); batch=data['items'];rows.extend(batch)
   if len(batch)<100: break
   offset+=len(batch)
 folder=VAULT/'文献笔记'; notes=note_map(folder)
 if args.apply:
  create_missing_notes(rows,folder)
  notes=note_map(folder)
 rendered=render_index(rows,notes)
 if not args.apply: print(rendered);return
 dest=VAULT/'Zotero 项目文献实时索引.md'
 with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=VAULT,delete=False) as f:
  tmp=f.name;f.write(rendered)
 try: os.replace(tmp,dest)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 print(f'已更新 {dest}；已有文献笔记未覆盖。')
if __name__=='__main__':
 try:main()
 except (RuntimeError,OSError,KeyError) as exc:print(f'更新失败：{exc}',file=sys.stderr);sys.exit(1)
