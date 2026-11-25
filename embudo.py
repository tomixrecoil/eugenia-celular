"""Publica los posts del embudo MATERIALES (embudo.json) en hidroponía: Instagram + Facebook.

25/11 (Tomix: "Sí, programala"): semana 1 = 30-nov a 6-dic, a las 20:30 ART. Corre en GitHub
(embudo.yml) dos veces por noche; publica lo de HOY (hora de Argentina) que no esté en
estado_embudo.json. Cada red se anota apenas sale, así un reintento no la duplica.
No toca la cola, el stock ni las historias. Imágenes y videos: R2 reels/embudo-*, servidos por
la ruta /v/ del Worker (el bucket no es público).
Uso: python3 embudo.py            publica lo de hoy
     python3 embudo.py --probar   arma los contenedores de IG de todos los posts sin publicar
     python3 embudo.py --fecha 2026-11-30   publica esa fecha (a mano)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v21.0"
PAGINA = "615394648318530"          # Facebook de Ecosistema Hidropónico
IG = "17841462466436017"            # Instagram ecosistema.hidroponico
ESTADO = ROOT / "estado_embudo.json"


def log(*a):
    print(datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M"), *a, flush=True)


def api(metodo, ruta, **campos):
    datos = urllib.parse.urlencode(campos).encode()
    url = f"{GRAPH}/{ruta}"
    if metodo == "GET":
        req = urllib.request.Request(url + "?" + datos.decode())
    else:
        req = urllib.request.Request(url, data=datos, method="POST")
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{ruta}: {e.read().decode()[:400]}") from None


def token_pagina():
    tb = os.environ["META_PAGE_ACCESS_TOKEN"].strip()
    return api("GET", PAGINA, fields="access_token", access_token=tb)["access_token"]


def esperar_ig(cid, tok, minutos=10):
    for _ in range(minutos * 4):
        st = api("GET", cid, fields="status_code,status", access_token=tok)
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rechazó el contenedor {cid}: {st}")
        time.sleep(15)
    raise RuntimeError(f"Instagram no terminó de procesar {cid}")


def contenedor_ig(p, tok):
    """Arma el contenedor listo para publicar (sin publicar)."""
    if p["tipo"] == "reel":
        cid = api("POST", f"{IG}/media", media_type="REELS", video_url=p["media"][0], caption=p["texto"],
                  share_to_feed="true", access_token=tok)["id"]
    elif p["tipo"] == "imagen":
        cid = api("POST", f"{IG}/media", image_url=p["media"][0], caption=p["texto"], access_token=tok)["id"]
    else:
        hijos = []
        for u in p["media"]:
            h = api("POST", f"{IG}/media", image_url=u, is_carousel_item="true", access_token=tok)["id"]
            esperar_ig(h, tok, 3)
            hijos.append(h)
        cid = api("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(hijos),
                  caption=p["texto"], access_token=tok)["id"]
    esperar_ig(cid, tok)
    return cid


def publicar_ig(p, tok):
    cid = contenedor_ig(p, tok)
    return api("POST", f"{IG}/media_publish", creation_id=cid, access_token=tok)["id"]


def publicar_fb(p, tok):
    if p["tipo"] == "reel":
        return api("POST", f"{PAGINA}/videos", file_url=p["media"][0], description=p["texto"],
                   access_token=tok)["id"]
    if p["tipo"] == "imagen":
        return api("POST", f"{PAGINA}/photos", url=p["media"][0], message=p["texto"], access_token=tok)["id"]
    fotos = [api("POST", f"{PAGINA}/photos", url=u, published="false", access_token=tok)["id"] for u in p["media"]]
    adj = {f"attached_media[{i}]": json.dumps({"media_fbid": f}) for i, f in enumerate(fotos)}
    return api("POST", f"{PAGINA}/feed", message=p["texto"], access_token=tok, **adj)["id"]


def main():
    posts = json.loads((ROOT / "embudo.json").read_text(encoding="utf-8"))["posts"]
    tok = token_pagina()
    if "--probar" in sys.argv:
        for p in posts:
            log(p["fecha"], p["tipo"], "contenedor IG listo:", contenedor_ig(p, tok))
        return 0
    hoy = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")
    if "--fecha" in sys.argv:
        hoy = sys.argv[sys.argv.index("--fecha") + 1]
    est = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
    error = 0
    for p in [x for x in posts if x["fecha"] == hoy]:
        hecho = est.setdefault(p["fecha"], {})
        for red, fn in (("ig", publicar_ig), ("fb", publicar_fb)):
            if red in hecho:
                log(p["fecha"], red, "ya salió:", hecho[red])
                continue
            try:
                hecho[red] = fn(p, tok)
                log(p["fecha"], p["tipo"], red, "publicado:", hecho[red])
            except Exception as e:  # noqa: BLE001
                error = 1
                log(p["fecha"], p["tipo"], red, "FALLÓ:", str(e)[:400])
            ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    if not any(x["fecha"] == hoy for x in posts):
        log("hoy", hoy, "no hay post del embudo")
    return error


if __name__ == "__main__":
    sys.exit(main())
