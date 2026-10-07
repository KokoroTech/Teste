import os, re, shutil, tempfile, subprocess, math
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import numpy as np
import cv2

BASE=Path(__file__).resolve().parent.parent
REF=BASE/"reference_images"
app=FastAPI(title="Roblox Finder API")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

def img_vec(img):
    img=img.convert("RGB").resize((128,128))
    a=np.asarray(img,dtype=np.float32)/255
    # Color histogram + low-resolution grayscale gives a cheap visual fingerprint.
    hist=[]
    for c in range(3):
        h,_=np.histogram(a[:,:,c],bins=16,range=(0,1),density=True)
        hist.extend(h/(np.linalg.norm(h)+1e-8))
    gray=cv2.cvtColor((a*255).astype(np.uint8),cv2.COLOR_RGB2GRAY)
    small=cv2.resize(gray,(32,32)).astype(np.float32)/255
    return np.concatenate([np.array(hist,dtype=np.float32),small.flatten()])

def load_refs():
    refs=[]
    if not REF.exists(): return refs
    for game_dir in REF.iterdir():
        if not game_dir.is_dir(): continue
        vecs=[]
        for p in game_dir.iterdir():
            if p.suffix.lower() not in [".jpg",".jpeg",".png",".webp"]: continue
            try: vecs.append(img_vec(Image.open(p)))
            except: pass
        if vecs: refs.append((game_dir.name,vecs))
    return refs

def score(a,b):
    # cosine similarity mapped to 0..1
    return float((np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-8)+1)/2)

def classify(pil):
    refs=load_refs()
    if not refs: return []
    a=img_vec(pil); out=[]
    for name,vecs in refs:
        s=max(score(a,v) for v in vecs)
        out.append((name,s))
    return sorted(out,key=lambda x:x[1],reverse=True)

def frame_results(video_path, fps_sample=2):
    cap=cv2.VideoCapture(str(video_path))
    fps=cap.get(cv2.CAP_PROP_FPS) or 30
    total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration=total/fps if total else 0
    step=max(1,int(fps/fps_sample))
    hits=[]
    i=0
    while True:
        ok,frame=cap.read()
        if not ok: break
        if i%step==0:
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            best=classify(Image.fromarray(rgb))
            if best and best[0][1]>=0.60:
                hits.append((i/fps,best[0][0],best[0][1]))
        i+=1
        if i>0 and i/fps>3600: break
    cap.release()
    return merge_hits(hits)

def merge_hits(hits):
    if not hits:return []
    merged=[]
    for t,g,s in hits:
        if not merged or merged[-1]["game"]!=g or t-merged[-1]["end"]>8:
            merged.append({"game":g,"start":t,"end":t,"score":s})
        else:
            merged[-1]["end"]=t
            merged[-1]["score"]=max(merged[-1]["score"],s)
    return merged

def save_upload(upload):
    suffix=Path(upload.filename or "").suffix or ".bin"
    fd,path=tempfile.mkstemp(suffix=suffix);os.close(fd)
    with open(path,"wb") as f: shutil.copyfileobj(upload.file,f)
    return Path(path)

@app.get("/api/health")
def health(): return {"ok":True,"reference_games":[x[0] for x in load_refs()]}

@app.post("/api/analyze/image")
async def analyze_image(file:UploadFile=File(...)):
    p=save_upload(file)
    try:
        best=classify(Image.open(p))
        return {"results":[{"game":g,"score":s} for g,s in best[:5] if s>=.60]}
    finally:p.unlink(missing_ok=True)

@app.post("/api/analyze/video")
async def analyze_video(file:UploadFile=File(...)):
    p=save_upload(file)
    try:return {"results":frame_results(p)}
    finally:p.unlink(missing_ok=True)

class YT(BaseModel): url:str

@app.post("/api/analyze/youtube")
async def analyze_youtube(data:YT):
    if not re.match(r"^https?://(www\.)?(youtube\.com|youtu\.be)/",data.url):
        raise HTTPException(400,"URL do YouTube inválida.")
    td=Path(tempfile.mkdtemp());out=td/"video.mp4"
    try:
        cmd=["yt-dlp","--no-playlist","-f","mp4[height<=720]/mp4","-o",str(out),data.url]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
        if proc.returncode!=0 or not out.exists():
            raise HTTPException(500,"Não foi possível baixar o vídeo. Verifique a URL e o servidor.")
        return {"results":frame_results(out)}
    finally:shutil.rmtree(td,ignore_errors=True)
