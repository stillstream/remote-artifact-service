from pathlib import Path
from urllib.parse import quote
import mimetypes

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.responses import Response

from .config import AppConfig


def resolve(root: Path, relative: str, show_hidden: bool) -> Path:
    raw = Path(relative or ".")
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(400, "invalid relative path")
    if not show_hidden and any(p.startswith(".") for p in raw.parts if p not in {"", "."}):
        raise HTTPException(404, "not found")
    target = (root / raw).resolve(strict=False)
    try:
        target.relative_to(root.resolve(strict=True))
    except ValueError:
        raise HTTPException(403, "path escapes configured root")
    if not target.exists():
        raise HTTPException(404, "not found")
    return target


def stream_file(path: Path, start: int = 0, length: int | None = None):
    with path.open("rb") as f:
        f.seek(start)
        left = length if length is not None else path.stat().st_size - start
        while left > 0:
            chunk = f.read(min(1024 * 1024, left))
            if not chunk:
                break
            left -= len(chunk)
            yield chunk


def mime(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt", ".log", ".csv", ".json", ".yaml", ".yml", ".py", ".sh"}:
        return "text/plain; charset=utf-8"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(title="Remote Artifact Service", docs_url=None, redoc_url=None)

    def get_root(root_id: str):
        for root in config.roots:
            if root.id == root_id:
                return root
        raise HTTPException(404, "unknown root")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Remote Artifact Service</title><style>body{font:15px system-ui;max-width:1000px;margin:32px auto;padding:0 16px;color:#222}a{color:#1769aa;text-decoration:none}.item{padding:10px;border-bottom:1px solid #ddd}.muted{color:#777}</style><h1>Remote Artifact Service</h1><p class='muted'>只读远程文件浏览 · 文件保留在设备本地</p><main id='app'>加载中…</main><script>
const app=document.querySelector('#app');const esc=s=>String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;',\"'\":'&#39;'}[c]));let root='';async function roots(){let d=await(await fetch('/api/roots')).json();app.innerHTML=d.roots.map(x=>`<div class=item><a href='#' data-root='${esc(x.id)}'>📁 ${esc(x.label)}</a></div>`).join('')}async function browse(p=''){let q=new URLSearchParams({root_id:root,path:p});let d=await(await fetch('/api/entries?'+q)).json();app.innerHTML=`<p><a href='#' data-home='1'>根目录</a> / ${esc(p)}</p>`+d.entries.map(x=>{let n=[p,x.name].filter(Boolean).join('/');let u='/view/'+encodeURIComponent(root)+'/'+n.split('/').map(encodeURIComponent).join('/');return `<div class=item>${x.is_dir?'📁':'📄'} <a href='${x.is_dir?'#':u}' ${x.is_dir?`data-path='${esc(n)}' target='_self'`:'target=_blank'}>${esc(x.name)}</a> <span class=muted>${x.is_dir?'目录':x.size+' B'}</span></div>`}).join('')}app.addEventListener('click',e=>{let a=e.target.closest('a');if(!a)return;if(a.dataset.root){e.preventDefault();root=a.dataset.root;browse()}else if(a.dataset.home){e.preventDefault();browse()}else if(a.dataset.path!==undefined){e.preventDefault();browse(a.dataset.path)}});roots();
</script></main>"""

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "remote-artifact-service", "version": "0.1.0"}

    @app.get("/api/roots")
    def roots():
        return {"roots": [{"id": r.id, "label": r.label} for r in config.roots]}

    @app.get("/api/entries")
    def entries(root_id: str, path: str = ""):
        r = get_root(root_id)
        folder = resolve(r.path, path, r.show_hidden)
        if not folder.is_dir():
            raise HTTPException(400, "not a directory")
        result = []
        for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            rel = str((Path(path) / item.name).as_posix()).lstrip("./")
            try:
                target = resolve(r.path, rel, r.show_hidden)
            except HTTPException:
                continue
            st = target.stat()
            result.append({"name": item.name, "is_dir": target.is_dir(), "size": st.st_size if target.is_file() else None, "mtime": int(st.st_mtime)})
        return {"root_id": root_id, "path": path, "entries": result}

    @app.get("/api/file")
    def file(root_id: str, path: str, request: Request):
        r = get_root(root_id); target = resolve(r.path, path, r.show_hidden)
        if not target.is_file(): raise HTTPException(400, "not a file")
        size = target.stat().st_size; start, end, status = 0, max(size - 1, 0), 200
        value = request.headers.get("range")
        if value:
            import re
            m = re.fullmatch(r"bytes=(\\d*)-(\\d*)", value.strip())
            if not m: raise HTTPException(416, "invalid range")
            a,b=m.groups()
            if not a and not b: raise HTTPException(416, "invalid range")
            start = max(0,size-int(b)) if not a else int(a)
            end = int(b) if a and b else size-1
            if start >= size or end < start: return Response(status_code=416,headers={"Content-Range":f"bytes */{size}"})
            end=min(end,size-1);status=206
        length=max(0,end-start+1);headers={"Accept-Ranges":"bytes","Content-Length":str(length),"X-Content-Type-Options":"nosniff","Cache-Control":"no-store"}
        if status==206: headers["Content-Range"]=f"bytes {start}-{end}/{size}"
        return StreamingResponse(stream_file(target,start,length),status_code=status,media_type=mime(target),headers=headers)

    @app.get("/view/{root_id}/{path:path}")
    def view(root_id: str, path: str):
        r=get_root(root_id);target=resolve(r.path,path,r.show_hidden)
        if not target.is_file(): raise HTTPException(400,"not a file")
        headers={"X-Content-Type-Options":"nosniff","Cache-Control":"no-store"}
        if target.suffix.lower() in {".html",".htm"}:
            headers["Content-Security-Policy"]="sandbox allow-scripts; default-src 'self' data: blob:; img-src 'self' data: blob:; media-src 'self' data: blob:; style-src 'self' 'unsafe-inline';"
        return StreamingResponse(stream_file(target),media_type=mime(target),headers=headers)

    @app.get("/api/download")
    def download(root_id: str,path: str):
        r=get_root(root_id);target=resolve(r.path,path,r.show_hidden)
        if not target.is_file(): raise HTTPException(400,"not a file")
        return StreamingResponse(stream_file(target),media_type="application/octet-stream",headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(target.name)}","Content-Length":str(target.stat().st_size),"X-Content-Type-Options":"nosniff"})
    return app
