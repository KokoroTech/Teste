# Roblox Finder — versão com backend real

## O que esta versão faz
- Analisa imagens no servidor.
- Analisa vídeos e extrai frames automaticamente.
- Agrupa frames consecutivos em intervalos.
- Aceita URL do YouTube e usa `yt-dlp` para baixar o vídeo.
- Compara frames com screenshots reais colocados em `reference_images/<NomeDoJogo>/`.

## Como adicionar jogos
Crie:
reference_images/
  Blox Fruits/
    1.jpg
    2.jpg
  Brookhaven RP/
    1.jpg
    2.jpg

Quanto mais screenshots diferentes do jogo, melhor a comparação.

## Rodar localmente
Python 3.11+
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000

Abra `frontend/index.html`.

## Deploy
O Dockerfile permite subir o backend em serviços que aceitem Docker.
O frontend pode ficar em GitHub Pages/Cloudflare Pages e receber a URL da API.

## Limitação importante
Este motor já é uma análise visual real por comparação de características, mas ainda não é um modelo semântico de visão. Para reconhecer milhares de experiências com alta precisão, a próxima evolução é trocar o fingerprint por embeddings de um modelo de visão e ampliar o banco de referências.
