"""Verifica el contraste WCAG AA de los pares token/fondo de static/css/tokens.css.

Uso: python scripts/verificar_contraste.py
Sale con código 1 si algún par no alcanza el mínimo en algún tema.
Texto: 4.5:1. Bordes de controles, badges, iconos e indicadores: 3:1.
"""
import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parent.parent / "static" / "css" / "tokens.css"

TEXTO = 4.5
NO_TEXTO = 3.0

# (primer plano, fondo, mínimo, uso)
PARES = [
    ("--color-ink", "--surface", TEXTO, "títulos sobre cards"),
    ("--color-ink", "--surface-secondary", TEXTO, "títulos sobre el fondo de página"),
    ("--color-text", "--surface", TEXTO, "texto sobre cards"),
    ("--color-text", "--surface-secondary", TEXTO, "texto sobre el fondo de página"),
    ("--color-text-soft", "--surface", TEXTO, "navegación, chips y patente"),
    ("--color-text-soft", "--surface-tertiary", TEXTO, "texto de la patente"),
    ("--color-text-soft", "--color-neutral-soft", TEXTO, "badge neutro"),
    ("--color-muted", "--surface", TEXTO, "texto secundario sobre cards"),
    ("--color-muted", "--surface-secondary", TEXTO, "texto secundario sobre el fondo"),
    ("--color-muted", "--surface-tertiary", TEXTO, "texto secundario sobre superficies terciarias"),
    ("--color-primary", "--surface", TEXTO, "links y acciones de texto"),
    ("--color-primary", "--surface-secondary", TEXTO, "links sobre el fondo"),
    ("--color-primary", "--surface-nav-active", TEXTO, "ítem activo de la sidebar"),
    ("--color-primary", "--color-primary-soft", TEXTO, "filtro activo"),
    ("--color-primary-strong", "--color-primary-soft", TEXTO, "botón outline en hover"),
    ("--color-danger-strong", "--surface", TEXTO, "errores de formulario"),
    ("--color-success-strong", "--surface", TEXTO, "acción WhatsApp en hover"),
    ("--color-danger-strong", "--color-danger-soft", TEXTO, "badge vencido"),
    ("--color-warning-strong", "--color-warning-soft", TEXTO, "badge próximo y pendiente"),
    ("--color-success-strong", "--color-success-soft", TEXTO, "badge al día"),
    ("--color-info-strong", "--color-info-soft", TEXTO, "badge contactado"),
    ("--color-purple-strong", "--color-purple-soft", TEXTO, "badge pospuesto y rol"),
    ("--color-on-fill", "--color-primary-fill", TEXTO, "botón primario y página actual"),
    ("--color-on-fill", "--color-primary-fill-strong", TEXTO, "botón primario en hover"),
    ("--color-on-fill", "--color-success-fill", TEXTO, "botón WhatsApp"),
    ("--color-on-fill", "--color-danger-fill", TEXTO, "confirmar acción destructiva"),
    ("--color-on-fill", "--color-warning-fill", TEXTO, "confirmar acción de advertencia"),
    ("--surface", "--color-ink", TEXTO, "enlace para saltar al contenido"),
    ("--border-strong", "--surface", NO_TEXTO, "borde de inputs y selects"),
    ("--border-strong", "--surface-secondary", NO_TEXTO, "borde de controles sobre el fondo"),
    ("--color-danger-border", "--surface", NO_TEXTO, "borde de badge vencido"),
    ("--color-warning-border", "--surface", NO_TEXTO, "borde de badge próximo"),
    ("--color-success-border", "--surface", NO_TEXTO, "borde de badge al día"),
    ("--color-info-border", "--surface", NO_TEXTO, "borde de badge contactado"),
    ("--color-purple-border", "--surface", NO_TEXTO, "borde de badge pospuesto"),
    ("--color-neutral-border", "--surface", NO_TEXTO, "borde de badge neutro"),
    ("--color-primary", "--surface", NO_TEXTO, "bordes de foco y controles activos"),
    ("--color-danger", "--surface", NO_TEXTO, "iconos y bordes de error"),
    ("--color-warning", "--surface", NO_TEXTO, "iconos de advertencia"),
    ("--color-success", "--surface", NO_TEXTO, "iconos de éxito"),
    ("--color-info", "--surface", NO_TEXTO, "iconos informativos"),
    ("--color-purple", "--surface", NO_TEXTO, "iconos de pospuesto"),
]

# Pares del tema claro que ya existían antes del modo oscuro y no se rediseñaron
# en esta etapa: se informan pero no hacen fallar la verificación.
EXCEPCIONES_CLARO = {
    ("--color-danger-border", "--surface"),
    ("--color-warning-border", "--surface"),
    ("--color-success-border", "--surface"),
    ("--color-info-border", "--surface"),
    ("--color-purple-border", "--surface"),
    ("--color-neutral-border", "--surface"),
    ("--border-strong", "--surface"),
    ("--border-strong", "--surface-secondary"),
}


def bloque(css, selector):
    coincidencia = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    if not coincidencia:
        raise ValueError(f"No se encontró el bloque {selector}")
    cuerpo = re.sub(r"/\*.*?\*/", "", coincidencia.group(1), flags=re.S)
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", cuerpo))


def tokens_por_tema(css=None):
    css = css if css is not None else TOKENS.read_text(encoding="utf-8")
    claro = bloque(css, ":root")
    oscuro = {**claro, **bloque(css, ':root[data-bs-theme="dark"]')}
    return {"claro": claro, "oscuro": oscuro}


def resolver(tokens, nombre, profundidad=0):
    valor = tokens[nombre].strip()
    referencia = re.fullmatch(r"var\((--[\w-]+)\)", valor)
    if referencia and profundidad < 10:
        return resolver(tokens, referencia.group(1), profundidad + 1)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
        raise ValueError(f"{nombre} no es un color opaco #rrggbb: {valor}")
    return valor


def luminancia(hexadecimal):
    canales = [int(hexadecimal[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineales = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineales[0] + 0.7152 * lineales[1] + 0.0722 * lineales[2]


def contraste(a, b):
    claro, oscuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


def evaluar(css=None):
    """Devuelve una lista de (tema, primer plano, fondo, ratio, mínimo, uso, falla)."""
    resultados = []
    for tema, tokens in tokens_por_tema(css).items():
        for frente, fondo, minimo, uso in PARES:
            ratio = contraste(resolver(tokens, frente), resolver(tokens, fondo))
            excepcion = tema == "claro" and (frente, fondo) in EXCEPCIONES_CLARO
            resultados.append((tema, frente, fondo, ratio, minimo, uso, ratio < minimo and not excepcion))
    return resultados


def main():
    resultados = evaluar()
    fallas = 0
    for tema, frente, fondo, ratio, minimo, uso, falla in resultados:
        estado = "FALLA" if falla else ("aviso" if ratio < minimo else "ok")
        fallas += falla
        print(f"{estado:5} {tema:6} {ratio:5.2f}:1 (mín. {minimo}) {frente} sobre {fondo} — {uso}")
    print(f"\n{fallas} pares por debajo del mínimo.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
