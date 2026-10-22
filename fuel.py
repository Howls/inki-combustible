#!/usr/bin/env python3
"""
Precio medio de Gasolina 95 y Gasoil en Vilanova i la Geltru.

Consulta la API publica del Ministerio (precios de carburantes), saca la
media del municipio, la anade a history.csv y genera data.json con lo que
necesita la placa: ultimos 7 dias, variacion y una frase.

Uso:
  python fuel.py                      # consulta la API real
  python fuel.py --sample muestra.json --date 2026-10-22   # prueba offline
"""
import argparse
import csv
import json
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ---------------- Configuracion ----------------
PROVINCIA_ID = "08"                      # Barcelona
MUNICIPIO_MATCH = "vilanova i la geltru" # comparacion sin tildes ni mayusculas
MUNICIPIO_LABEL = "Vilanova i la Geltru"
API_URL = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
           "PreciosCarburantes/EstacionesTerrestres/FiltroProvincia/" + PROVINCIA_ID)
HEADERS = {
    # En foros comentan que la API a veces exige cabeceras de navegador
    "User-Agent": "Mozilla/5.0 (compatible; inki-combustible/1.0)",
    "Accept": "application/json",
    "Referer": "https://sedeaplicaciones.minetur.gob.es/",
    "Origin": "https://sedeaplicaciones.minetur.gob.es",
}
# Nombres de campo en el JSON de la API (si cambian, el script lo dira)
F_MUNICIPIO = "Municipio"
F_G95 = "Precio Gasolina 95 E5"
F_GASOIL = "Precio Gasoleo A"

HISTORY = Path("history.csv")
OUTPUT = Path("data.json")
TZ = ZoneInfo("Europe/Madrid")

# Umbrales (euros/litro) para la frase, sobre la ventana de ~5 dias
UMBRAL_FUERTE = 0.030
UMBRAL_SUAVE = 0.015


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def parse_price(v):
    if v is None:
        return None
    v = str(v).strip().replace(",", ".")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def load_response(sample):
    if sample:
        raw = Path(sample).read_bytes()
    else:
        r = requests.get(API_URL, headers=HEADERS, timeout=90)
        r.raise_for_status()
        raw = r.content
    # utf-8-sig por si la respuesta trae BOM
    return json.loads(raw.decode("utf-8-sig"))


def municipal_averages(data):
    estaciones = data.get("ListaEESSPrecio")
    if not estaciones:
        sys.exit("La respuesta no trae 'ListaEESSPrecio'. Claves recibidas: "
                 + ", ".join(data.keys()))
    for campo in (F_MUNICIPIO, F_G95, F_GASOIL):
        if campo not in estaciones[0]:
            sys.exit(f"No encuentro el campo '{campo}'. Campos disponibles: "
                     + ", ".join(estaciones[0].keys()))

    locales = [e for e in estaciones if norm(e[F_MUNICIPIO]) == MUNICIPIO_MATCH]
    if not locales:
        parecidos = sorted({e[F_MUNICIPIO] for e in estaciones
                            if "vilanova" in norm(e[F_MUNICIPIO])})
        sys.exit("Ninguna estacion en el municipio. Parecidos: " + str(parecidos))

    g95 = [p for p in (parse_price(e[F_G95]) for e in locales) if p is not None]
    gas = [p for p in (parse_price(e[F_GASOIL]) for e in locales) if p is not None]
    if not g95 or not gas:
        sys.exit("Hay estaciones pero sin precio de G95 o gasoil.")
    return sum(g95) / len(g95), sum(gas) / len(gas), len(locales)


def read_history():
    rows = {}
    if HISTORY.exists():
        with HISTORY.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["fecha"]] = {"g95": float(r["g95"]),
                                    "gasoil": float(r["gasoil"]),
                                    "n": int(r["n"])}
    return rows


def write_history(rows):
    with HISTORY.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fecha", "g95", "gasoil", "n"])
        for d in sorted(rows):
            r = rows[d]
            w.writerow([d, f"{r['g95']:.4f}", f"{r['gasoil']:.4f}", r["n"]])


def frase(window):
    """Describe la tendencia reciente. No predice nada."""
    if len(window) < 3:
        return "Recogiendo datos, vuelve en unos dias"
    d_g95 = window[-1]["g95"] - window[0]["g95"]
    d_gas = window[-1]["gasoil"] - window[0]["gasoil"]
    d = (d_g95 + d_gas) / 2
    if d >= UMBRAL_FUERTE:
        return "Sube fuerte: llena hoy"
    if d >= UMBRAL_SUAVE:
        return "Va subiendo: mejor llenar ya"
    if d <= -UMBRAL_FUERTE:
        return "Baja fuerte: aguanta un poco"
    if d <= -UMBRAL_SUAVE:
        return "Va bajando: aguanta un poco"
    return "Estable: llena cuando te toque"


def build_output(rows, today):
    fechas = sorted(rows)[-7:]
    serie = [rows[d] for d in fechas]
    window = serie[-6:]  # hasta 5 intervalos

    def fuel(key):
        vals = [round(r[key], 3) for r in serie]
        delta = round(serie[-1][key] - serie[-2][key], 3) if len(serie) > 1 else 0.0
        return {"hoy": vals[-1], "delta": delta, "serie": vals}

    return {
        "fecha": today,
        "municipio": MUNICIPIO_LABEL,
        "estaciones": serie[-1]["n"],
        "dias": [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d in fechas],
        "g95": fuel("g95"),
        "gasoil": fuel("gasoil"),
        "frase": frase(window),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="JSON local en vez de consultar la API")
    ap.add_argument("--date", help="fecha YYYY-MM-DD (para pruebas)")
    args = ap.parse_args()

    today = args.date or datetime.now(TZ).date().isoformat()
    data = load_response(args.sample)
    g95, gas, n = municipal_averages(data)

    rows = read_history()
    rows[today] = {"g95": g95, "gasoil": gas, "n": n}  # idempotente por dia
    write_history(rows)

    out = build_output(rows, today)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=True, indent=1), encoding="utf-8")
    print(f"{today}: G95 {g95:.3f} | Gasoil {gas:.3f} | {n} estaciones | {out['frase']}")


if __name__ == "__main__":
    main()
