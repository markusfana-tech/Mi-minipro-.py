# Python SysOps CLI (Monitor, Backup & Clean Tool)

Este proyecto es una herramienta de administración de sistemas y automatización en Python diseñada para ejecutarse desde la terminal (CLI). Cumple con cinco de los objetivos principales del curso final en un conjunto minimalista de archivos.

## Características

1. **Monitoreo de Recursos en Tiempo Real**: Visualización en tiempo real del uso de CPU, RAM, Disco y tráfico de red en un tablero estilizado para la terminal.
2. **Registro Histórico de Métricas**: Exportación automática de las métricas recolectadas a un archivo local estructurado (`metrics_log.json`).
3. **Automatización de Respaldos (Backups)**: Compresión de directorios en formato ZIP con un esquema de retención inteligente (mantiene solo los últimos $N$ respaldos y elimina los más antiguos).
4. **Limpieza Automatizada de Archivos**: Eliminación programada de archivos viejos (como logs o archivos temporales) basada en un patrón de nombres y edad del archivo en días.
5. **Integración con APIs Externas**:
   - Detección automática de la IP pública y su geolocalización al iniciar el monitoreo mediante una API web de geolocalización.
   - Envío de alertas vía Webhook HTTP (formato compatible con Discord, Slack, etc.) si se superan los límites configurados de uso de hardware o al completarse exitosamente una copia de seguridad.

---

## Estructura del Proyecto

* **`sysops.py`**: El script principal que contiene toda la lógica de los comandos y clases.
* **`requirements.txt`**: Definición de las dependencias necesarias.
* **`README.md`**: Este archivo con las instrucciones de uso.

---

## Requisitos e Instalación

Este proyecto requiere Python 3.7 o superior.

### 1. Crear un Entorno Virtual (Recomendado)
Para evitar conflictos de dependencias globales, crea y activa un entorno virtual en la carpeta del proyecto:

**En Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**En Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar Dependencias
Una vez activado el entorno, instala los paquetes necesarios mediante `pip`:
```bash
pip install -r requirements.txt
```

Las librerías requeridas son:
* `psutil`: Lectura de estadísticas de hardware.
* `requests`: Consumo de la API de geolocalización y webhooks.
* `colorama`: Formateo de colores multiplataforma en la terminal.

---

## Guía de Uso del CLI

El comando principal es `sysops.py`. Tiene tres subcomandos: `monitor`, `backup` y `clean`.

### 1. Monitoreo del Sistema (`monitor`)

Muestra el dashboard interactivo en tiempo real en la terminal, guarda los datos en `metrics_log.json` y valida umbrales de alerta.

```bash
python sysops.py monitor [opciones]
```

**Opciones disponibles:**
* `--interval SECS`: Tiempo de refresco del dashboard en segundos (por defecto: `3`).
* `--once`: Si se especifica, toma una única lectura de hardware, la registra y sale inmediatamente del programa.
* `--log-file RUTA`: Especifica dónde guardar el historial JSON (por defecto: `metrics_log.json`).
* `--webhook URL`: Dirección URL del Webhook para enviar alertas en caso de sobrepasar los umbrales de hardware.
* `--cpu-alert PCT`: Límite de advertencia de CPU en porcentaje (por defecto: `80.0`).
* `--mem-alert PCT`: Límite de advertencia de memoria RAM en porcentaje (por defecto: `80.0`).
* `--disk-alert PCT`: Límite de advertencia de espacio de disco en porcentaje (por defecto: `90.0`).

**Ejemplo de ejecución en bucle:**
```bash
python sysops.py monitor --interval 5 --cpu-alert 75 --webhook "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
```

**Ejemplo para una sola lectura (útil para cronjobs):**
```bash
python sysops.py monitor --once
```

---

### 2. Copias de Seguridad Automatizadas (`backup`)

Comprime recursivamente una carpeta origen a un archivo ZIP en un directorio destino, aplicando políticas de rotación de respaldos.

```bash
python sysops.py backup --src <origen> --dest <destino> [opciones]
```

**Opciones disponibles:**
* `--src RUTA` *(Requerido)*: Carpeta que deseas respaldar.
* `--dest RUTA` *(Requerido)*: Carpeta donde se guardará el archivo `.zip`.
* `--keep N`: Cantidad máxima de respaldos históricos que deseas conservar para ese origen. Eliminará los respaldos más antiguos si excede este número (por defecto: `5`).
* `--webhook URL`: Envía un mensaje de éxito/error al Webhook con los metadatos del respaldo (tamaño del archivo, tiempo de ejecución, etc.).

**Ejemplo de ejecución:**
```bash
python sysops.py backup --src ./mi_codigo --dest ./respaldos --keep 3
```

---

### 3. Limpieza de Archivos Antiguos (`clean`)

Escanea un directorio para eliminar archivos viejos que coincidan con el patrón indicado, ayudando a limpiar temporales o logs que consumen disco.

```bash
python sysops.py clean --dir <directorio> [opciones]
```

**Opciones disponibles:**
* `--dir RUTA` *(Requerido)*: Directorio donde se ejecutará la limpieza.
* `--pattern PATRON`: Patrón de nombres de archivo a filtrar (por defecto: `*.log`).
* `--age DIAS`: Elimina solo los archivos cuya última modificación sea mayor a este número de días (por defecto: `7`).

**Ejemplo de ejecución:**
```bash
python sysops.py clean --dir ./servidor/logs --pattern "*.log" --age 15
```

---

## Formato del Historial de Monitoreo (`metrics_log.json`)

El comando `monitor` registra las métricas en un arreglo JSON estructurado. Mantiene automáticamente hasta 100 lecturas históricas:

```json
[
    {
        "timestamp": "2026-06-03T02:08:00.123456",
        "cpu_percent": 12.5,
        "memory_percent": 64.2,
        "memory_used_gb": 10.272,
        "memory_total_gb": 16.0,
        "disk_percent": 45.8,
        "disk_used_gb": 229.0,
        "disk_total_gb": 500.0,
        "net_sent_kb_s": 14.2,
        "net_recv_kb_s": 112.8
    }
]
```
