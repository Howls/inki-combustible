# inki-combustible

Una vez al dia calcula el precio medio de Gasolina 95 y Gasoil en
Vilanova i la Geltru (API publica del Ministerio), guarda el historico en
`history.csv` y genera `data.json` para la pantalla e-paper.

## Probar en tu PC (haz esto primero)

    pip install -r requirements.txt
    python fuel.py

Si todo va bien imprime algo como `2026-10-22: G95 1.4xx | Gasoil 1.3xx | N estaciones | ...`
y crea `history.csv` y `data.json`. Si falla, el mensaje de error dice que
campo o municipio no ha encontrado.

La frase describe la tendencia de los ultimos ~5 dias; no predice nada.
Hasta tener 3 dias de datos dice "Recogiendo datos".

## Automatizar (GitHub Actions)

1. Crea un repo **publico** (la placa lo descargara sin token) y sube esto.
2. En Actions, lanza "Precio combustible" a mano una vez (workflow_dispatch).
3. Desde ahi corre solo cada dia ~07:30-08:30 (hora Espana).

Ojo: GitHub desactiva los workflows programados tras ~60 dias sin actividad
en el repo. Como el propio workflow hace commits a diario deberia mantenerse
activo, pero no lo he verificado.

Si desde los servidores de GitHub la API del Ministerio no responde, el
script se puede ejecutar desde un PC o una Raspberry con cron.
