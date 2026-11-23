"""Borra historias viejas de una cuenta desde el Instagram del emulador (23/11, Tomix: borrar
las historias con el botón mal puesto). La API de Meta no deja borrar historias.

Uso: python3 borrar_historias.py hidroponia@16:55,bonsai@15:43   (hora UTC de la historia)
Solo borra si es la historia MÁS VIEJA de la cuenta (Instagram abre las propias desde la
primera) y si la antigüedad que muestra el visor ("5 h") coincide con la de esa historia.
Cualquier duda: no borra. Después confirma con la API que se fue esa y quedaron las otras.
"""
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import historia_emulador as he
import historias_nube as hn


def vivas(n):
    tb = os.environ["META_PAGE_ACCESS_TOKEN"].strip()
    tok = json.load(urllib.request.urlopen(
        f"{hn.GRAPH}/{hn.CUENTAS[n][1]}?fields=access_token&access_token={tb}", timeout=60))["access_token"]
    s = json.load(urllib.request.urlopen(
        f"{hn.GRAPH}/{hn.IG_ID[n]}/stories?fields=timestamp&access_token={tok}", timeout=60))
    return sorted(x["timestamp"][:19] for x in s.get("data", []))


def foto(nombre):
    with open(f"falla_{nombre}.png", "wb") as f:
        f.write(subprocess.run([he.ADB, "-s", "emulator-5554", "exec-out", "screencap", "-p"],
                               capture_output=True).stdout)


def horas(ts):
    t = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - t).total_seconds() // 3600)


def borrar(n, hhmm):
    antes = vivas(n)
    print(n, "antes:", [x[11:16] for x in antes], flush=True)
    if not antes or antes[0][11:16] != hhmm:
        print(f"  {n}: la de {hhmm} no es la más vieja (o ya no está): no borro nada", flush=True)
        return False
    objetivo = antes[0]
    he.cambiar_cuenta(hn.CUENTAS[n][0])
    tab = he.buscar(r"^(Profile|Perfil)$")
    if not tab:
        foto(f"{n}_sin_perfil"); print("  no encontré la pestaña de perfil"); return False
    he.tocar(tab); time.sleep(4)
    ns = he.nodos()
    # La foto del perfil, arriba a la izquierda (23/11: en hidroponía "story" agarraba la
    # nota del perfil y abría el editor de notas).
    cand = [x for x in ns if re.search(r"story|historia|profile picture|foto del perfil", x["desc"], re.I)
            and not re.search(r"note|nota|thought", x["desc"] + x["text"], re.I)
            and (x["b"][0] + x["b"][2]) // 2 < 450 and x["b"][1] < 1000]
    if not cand:
        foto(f"{n}_sin_avatar"); print("  no encontré la foto del perfil"); return False
    he.tocar(cand[0]); time.sleep(2.5)
    # Instagram abre en la primera historia NO vista, no en la más vieja: se retrocede
    # tocando el borde izquierdo hasta la primera (en la primera, tocar ahí no hace nada).
    for _ in range(len(antes) + 2):
        he.adb("shell", "input", "tap", "60", "1300"); time.sleep(0.6)
    if not he.tocar_texto(r"^(More|Más|Menu|Menú|Opciones|Options)$", 6):
        foto(f"{n}_sin_mas"); print("  no encontré el botón Más en el visor"); return False
    time.sleep(1.5)
    ns = he.nodos()
    foto(f"{n}_menu")
    # Antigüedad que muestra el visor: tiene que ser la de la historia a borrar
    edad = None
    for x in ns:
        m = re.fullmatch(r"\s*(\d+)\s*(h|hr|hrs|hours?|horas?)\s*", x["text"] or x["desc"], re.I)
        if m:
            edad = int(m.group(1)); break
    esperada = horas(objetivo)
    otras = {horas(t) for t in antes[1:]}
    print(f"  visor: {edad} h; la historia a borrar tiene {esperada} h; las otras {sorted(otras)}", flush=True)
    if edad is None or edad not in (esperada, esperada + 1) or edad in otras:
        he.adb("shell", "input", "keyevent", "4"); time.sleep(1)
        print("  no estoy seguro de que sea la vieja: no borro", flush=True)
        return False
    if not he.tocar_texto(r"^(Delete|Eliminar|Borrar)$", 6):
        foto(f"{n}_sin_eliminar"); print("  no encontré Eliminar"); return False
    time.sleep(1.5)
    if not he.tocar_texto(r"^(Delete|Eliminar|Borrar)$", 6):
        foto(f"{n}_sin_confirmar"); print("  no encontré la confirmación"); return False
    time.sleep(6)
    he.adb("shell", "input", "keyevent", "4"); time.sleep(1)
    Path("guardar_avd").write_text("1")
    despues = vivas(n)
    print(n, "después:", [x[11:16] for x in despues], flush=True)
    ok = objetivo not in despues and set(antes[1:]) <= set(despues)
    print(f"  {n}: {'borrada' if ok else 'REVISAR: no quedó como esperaba'}", flush=True)
    return ok


if __name__ == "__main__":
    for par in (sys.argv[1] if len(sys.argv) > 1 else "").split(","):
        if "@" in par:
            n, hhmm = par.strip().split("@")
            try:
                borrar(n, hhmm)
            except SystemExit as e:
                print(f"  {n}: {e}", flush=True)
