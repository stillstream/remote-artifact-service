from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.responses import Response

from .config import AppConfig

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


def resolve(root: Path, relative: str, show_hidden: bool) -> Path:
    raw = Path(relative or ".")
    if raw.is_absolute() or ".." in raw.parts:
        raise HTTPException(400, "invalid relative path")
    if not show_hidden and any(part.startswith(".") for part in raw.parts if part not in {"", "."}):
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
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length if length is not None else path.stat().st_size - start
        while remaining > 0:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def media_type(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt", ".log", ".csv", ".json", ".yaml", ".yml", ".py", ".sh"}:
        return "text/plain; charset=utf-8"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def ranged_response(path: Path, request: Request, *, inline: bool = True) -> Response:
    size = path.stat().st_size
    start, end, status = 0, size - 1, 200
    value = request.headers.get("range")
    if value:
        match = _RANGE.fullmatch(value.strip())
        if not match:
            raise HTTPException(416, "invalid range")
        first, last = match.groups()
        if not first and not last:
            raise HTTPException(416, "invalid range")
        if not first:
            suffix = int(last)
            if suffix <= 0:
                raise HTTPException(416, "invalid range")
            start = max(0, size - suffix)
        else:
            start = int(first)
            if last:
                end = int(last)
        if start >= size or end < start:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        end = min(end, size - 1)
        status = 206
    length = max(0, end - start + 1)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    if not inline:
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(path.name)}"
    return StreamingResponse(
        stream_file(path, start, length),
        status_code=status,
        media_type=media_type(path) if inline else "application/octet-stream",
        headers=headers,
    )


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(title="Remote Artifact Service", docs_url=None, redoc_url=None)

    def get_root(root_id: str):
        for root in config.roots:
            if root.id == root_id:
                return root
        raise HTTPException(404, "unknown root")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Remote Artifact Service</title>
<style>
body{font:15px system-ui,sans-serif;max-width:1050px;margin:34px auto;padding:0 18px;color:#202124}
a{color:#1769aa;text-decoration:none}a:hover{text-decoration:underline}
.item{padding:11px 10px;border-bottom:1px solid #e5e7eb}.muted{color:#6b7280;font-size:13px}
header{margin-bottom:22px}h1{font-size:23px}
</style>
<header><h1>Remote Artifact Service</h1><div class="muted">只读远程文件浏览 · 文件保留在设备本地</div></header>
<main id="app">加载中…</main>
<script>
const app=document.getElementById("app");
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
let currentRoot="";
async function showRoots(){
 const response=await fetch("/api/roots"); const data=await response.json();
 app.innerHTML=data.roots.map(r=>'<div class="item">📁 <a href="#" data-root="'+esc(r.id)+'">'+esc(r.label)+'</a></div>').join("");
}
async function showDirectory(path){
 const query=new URLSearchParams({root_id:currentRoot,path:path||""});
 const response=await fetch("/api/entries?"+query);
 if(!response.ok){app.textContent="无法读取目录（"+response.status+"）";return;}
 const data=await response.json();
 let body='<div class="item"><a href="#" data-roots="1">全部目录</a> / '+esc(path||"")+'</div>';
 for(const entry of data.entries){
  const relative=[path,entry.name].filter(Boolean).join("/");
  const url="/view/"+encodeURIComponent(currentRoot)+"/"+relative.split("/").map(encodeURIComponent).join("/");
  body+='<div class="item">'+(entry.is_dir?"📁 ":"📄 ")+'<a href="'+(entry.is_dir?"#":url)+'" '+(entry.is_dir?'data-path="'+esc(relative)+'"':'target="_blank"')+'>'+esc(entry.name)+'</a><span class="muted"> '+(entry.is_dir?"目录":entry.size+" B")+'</span></div>';
 }
 app.innerHTML=body;
}
app.addEventListener("click",event=>{
 const link=event.target.closest("a"); if(!link)return;
 if(link.dataset.root){event.preventDefault();currentRoot=link.dataset.root;showDirectory("");}
 else if(link.dataset.roots){event.preventDefault();showRoots();}
 else if(link.dataset.path!==undefined){event.preventDefault();showDirectory(link.dataset.path);}
});
showRoots();
</script></main></html>"""

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "remote-artifact-service", "version": "0.1.0"}

    @app.get("/api/roots")
    def roots():
        return {"roots": [{"id": root.id, "label": root.label} for root in config.roots]}

    @app.get("/api/entries")
    def entries(root_id: str, path: str = ""):
        root = get_root(root_id)
        folder = resolve(root.path, path, root.show_hidden)
        if not folder.is_dir():
            raise HTTPException(400, "not a directory")
        result = []
        for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            relative = (Path(path) / item.name).as_posix()
            try:
                target = resolve(root.path, relative, root.show_hidden)
            except HTTPException:
                continue
            stat = target.stat()
            result.append({
                "name": item.name,
                "is_dir": target.is_dir(),
                "size": stat.st_size if target.is_file() else None,
                "mtime": int(stat.st_mtime),
            })
        return {"root_id": root_id, "path": path, "entries": result}

    @app.get("/api/file")
    def file(root_id: str, path: str, request: Request):
        target = resolve(get_root(root_id).path, path, get_root(root_id).show_hidden)
        if not target.is_file():
            raise HTTPException(400, "not a file")
        return ranged_response(target, request)

    @app.get("/view/{root_id}/{path:path}")
    def view(root_id: str, path: str, request: Request):
        target = resolve(get_root(root_id).path, path, get_root(root_id).show_hidden)
        if not target.is_file():
            raise HTTPException(400, "not a file")
        response = ranged_response(target, request)
        if target.suffix.lower() in {".html", ".htm"}:
            response.headers["Content-Security-Policy"] = (
                "sandbox allow-scripts; default-src 'self' data: blob:; "
                "img-src 'self' data: blob:; media-src 'self' data: blob:; "
                "style-src 'self' 'unsafe-inline';"
            )
        return response

    @app.get("/api/download")
    def download(root_id: str, path: str, request: Request):
        target = resolve(get_root(root_id).path, path, get_root(root_id).show_hidden)
        if not target.is_file():
            raise HTTPException(400, "not a file")
        return ranged_response(target, request, inline=False)

    return app
