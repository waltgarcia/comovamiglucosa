# ¿Cómo va mi glucosa?

Aplicación web para que pacientes registren sus cifras de glucosa en formato digital y las compartan de forma ordenada con su médico.

## Objetivo

- Reemplazar hojas en papel que pueden perderse o dañarse.
- Facilitar seguimiento clínico con datos estructurados.
- Permitir al doctor valorar tendencias y episodios con mejor contexto.

## Qué incluye

- Cuentas por paciente (`código de paciente` + `PIN de 4 dígitos`).
- Aislamiento de datos por paciente (cada uno ve solo su información).
- Registro de glucosa simplificado con 3 opciones:
  - Antes de la comida
  - Después de la comida
  - Glucosa al azar
- Fecha y hora automáticas al guardar registros.
- Campo de unidades si se selecciona insulina.
- Recomendaciones inmediatas según valor de glucosa.
- Registro de HbA1c y eventos clínicos relevantes.
- Resumen automático (7/14/30 días, min/máx, % en rango, hipo/hiper).
- Gráficas de tendencia con rangos personalizados por el doctor.
- Historial editable y vista cronológica unificada.
- Exportación en 1 clic: CSV, Excel y PDF.
- Compartición segura mediante paquete cifrado (`.cmg`) con clave temporal.

## Flujo de uso

### Paciente

1. Crea cuenta en **Crear cuenta paciente**.
2. Define un código y un PIN de 4 números.
3. Registra mediciones y eventos en la pestaña **Registro**.
4. Exporta o comparte datos en **Exportar y compartir**.

### Doctor

Para revisar información de un paciente se requieren:

- Código del paciente.
- Archivo cifrado `.cmg`.
- Clave de cifrado temporal (enviada por canal separado).

Ejemplo de clave cifrada:

`bt65lYn_O4-K3bK-GgKE3nYRiey9j8hf9v7O-5ShTj8=`

Con esos elementos, el doctor puede usar el módulo de descifrado dentro de la app para valorar cifras y contexto clínico.

## Reglas de acceso

- El código de paciente puede ser numérico o alfanumérico.
- Se permiten letras, números, guion (`-`) y guion bajo (`_`).
- El PIN debe tener exactamente 4 dígitos numéricos.

## Instalación local

1. Instala dependencias:

```bash
pip install -r requirements.txt
```

2. Ejecuta la app:

```bash
streamlit run streamlit_app.py
```

> Importante: no usar `python streamlit_app.py`.

## Publicación en Streamlit Community Cloud

1. Sube el proyecto a GitHub.
2. Entra a https://share.streamlit.io y crea una app nueva.
3. Selecciona:
   - Repository: `waltgarcia/comovamiglucosa`
   - Branch: `main`
   - Main file path: `streamlit_app.py`

## Estructura del proyecto

- `streamlit_app.py`: interfaz principal y flujo de usuario.
- `app/db.py`: persistencia SQLite multi-paciente.
- `app/security.py`: hash de PIN y cifrado.
- `app/validation.py`: validaciones de entrada.
- `app/analytics.py`: métricas y línea de tiempo.
- `app/exporters.py`: exportación CSV/Excel/PDF y paquete cifrado.
- `tests/`: pruebas unitarias básicas.

## Solución de problemas

- **No puedo crear paciente nuevo**
  - Usa el botón lateral **Cambiar de paciente / Crear otro**.
  - Verifica que el código no exista.
  - Revisa formato de código y PIN.

- **PIN incorrecto**
  - Verifica que sean 4 dígitos exactos.
  - Confirma que ingresas el código correcto del paciente.

## Nota clínica

Esta herramienta es de apoyo y no reemplaza valoración médica. Ante valores extremos o síntomas de alarma, contactar servicios de salud.
