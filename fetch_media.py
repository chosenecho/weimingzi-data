#!/usr/bin/env python3
import argparse,hashlib,json,os,pathlib,shutil,sys,time,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def valid(path,row):return path.is_file() and path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
def target_path(name):
 p=pathlib.PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts or ':' in name or chr(92) in name:raise ValueError('Unsafe archive path: '+name)
 target=(ROOT/pathlib.Path(*p.parts)).resolve()
 if not target.is_relative_to(ROOT):raise ValueError('Archive path escapes repository')
 return target
def download(asset,cache):
 target=cache/asset['name']
 if valid(target,asset):return target
 partial=target.with_suffix(target.suffix+'.part')
 for attempt in range(1,4):
  try:
   request=urllib.request.Request(asset['url'],headers={'User-Agent':'weimingzi-data/1.0'})
   with urllib.request.urlopen(request,timeout=120) as response,partial.open('wb') as out:shutil.copyfileobj(response,out,4*1024*1024)
   if not valid(partial,asset):raise ValueError('Archive size or SHA-256 mismatch: '+asset['name'])
   os.replace(partial,target);return target
  except Exception:
   if attempt==3:raise
   time.sleep(2*attempt)
 raise RuntimeError('Download failed')
def main():
 parser=argparse.ArgumentParser(description='Download and verify the audio release assets; preserve original relative paths.')
 parser.add_argument('--verify-only',action='store_true');parser.add_argument('--asset',action='append',help='Only restore this archive (repeatable)');args=parser.parse_args()
 manifest=json.loads((ROOT/'media-manifest.json').read_text('utf-8'));known={a['name'] for a in manifest['assets']}
 if args.asset and not set(args.asset).issubset(known):parser.error('Unknown asset name')
 selected=[r for r in manifest['files'] if not args.asset or r['archive'] in args.asset]
 if args.verify_only:
  missing=[r['path'] for r in selected if not valid(target_path(r['path']),r)]
  print(json.dumps({'checked':len(selected),'missing_or_invalid':missing},ensure_ascii=False,indent=2));return 1 if missing else 0
 cache=ROOT/'.media-cache';cache.mkdir(exist_ok=True);count=0
 for asset in manifest['assets']:
  expected={r['path']:r for r in selected if r['archive']==asset['name']}
  if not expected:continue
  if all(valid(target_path(name),row) for name,row in expected.items()):count+=len(expected);continue
  print('Downloading '+asset['name'],flush=True);archive=download(asset,cache)
  with zipfile.ZipFile(archive) as z:
   members=z.infolist()
   if len(members)!=len(expected) or {m.filename for m in members}!=set(expected):raise ValueError('Unexpected archive members')
   for member in members:
    row=expected[member.filename];target=target_path(member.filename)
    if member.is_dir() or member.file_size!=row['bytes']:raise ValueError('Unexpected archive member size')
    if valid(target,row):continue
    target.parent.mkdir(parents=True,exist_ok=True);partial=target.with_suffix(target.suffix+'.part')
    with z.open(member) as source,partial.open('wb') as out:shutil.copyfileobj(source,out,4*1024*1024)
    if not valid(partial,row):raise ValueError('Audio SHA-256 mismatch: '+row['path'])
    os.replace(partial,target)
  count+=len(expected);print('Restored '+str(count)+' / '+str(len(selected)),flush=True)
 print('Audio verification complete: '+str(count)+' files');return 0
if __name__=='__main__':sys.exit(main())
