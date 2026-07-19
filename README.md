# Disk Integrity Checker

Herramienta de línea de comandos para generar inventarios de archivos con hashes y verificar que no hayan sido modificados, eliminados o agregados después de transferencias o copias de seguridad.

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

1. Copiar el archivo de variables de entorno:

   ```bash
   cp .env.example .env
   ```

2. Editar `.env` según el tipo de persistencia deseado:

   - `JSON`: define `JSON_DB_FOLDER`.
   - `MONGODB`: completa los datos de conexión (actualmente no implementado).

## Uso

El CLI expone dos comandos: `inventory` y `verify`.

### Generar un inventario

```bash
python src/presentation/cli/main.py inventory <directorio> \
  --output-file inventario.json \
  --hash-algo sha256 \
  --workers 4
```

Algoritmos soportados: `sha1`, `sha256`, `sha3_512`, `blake2b`.

### Verificar un directorio contra un inventario

```bash
python src/presentation/cli/main.py verify <directorio> \
  --inventory-file inventario.json \
  --hash-algo sha256 \
  --workers 4
```

El comando reporta:

- Archivos modificados (cambió el hash).
- Archivos faltantes.
- Archivos agregados.
- Errores de lectura.

## Estructura del repositorio

```txt
├── src/                       # Código fuente
│   ├── domain/                # Entidades y repositorios abstractos
│   ├── infrastructure/        # Implementaciones de persistencia y almacenamiento
│   └── presentation/cli/      # Interfaz de línea de comandos
├── tests/                     # Tests con pytest
├── .env.example               # Ejemplo de configuración
├── requirements.txt           # Dependencias
└── README.md                  # Este archivo
```

## Tests

```bash
python -m pytest tests -v
```

## Automatización

Se recomienda configurar tareas programadas (cron, systemd timers o Task Scheduler) para ejecutar los comandos `inventory` y `verify` periódicamente.
