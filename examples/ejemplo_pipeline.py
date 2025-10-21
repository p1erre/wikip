#!/usr/bin/env python3
"""
Ejemplo visual de cómo funcionan los pipelines

Este script demuestra paso a paso el flujo de los pipelines.
"""

from src.pipeline import generate_booklet, process_video

print("=" * 80)
print("EJEMPLO 1: Pipeline de Procesamiento Completo (process_video)")
print("=" * 80)
print()

# Este pipeline hace 4 cosas:
# 1. Normaliza la entrada (URL → video_id)
# 2. Extrae slides del video
# 3. Obtiene la transcripción de YouTube
# 4. Analiza los slides con Vision LLM (opcional)

video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

print("Procesando video completo...")
print(f"URL: {video_url}")
print()

# Ejecutar pipeline
result = process_video(
    input_source=video_url,
    skip_vision=True,  # Saltamos vision para ser más rápido
    force_reprocess=False,  # Usar cache si está disponible
)

print("Resultado:")
print(f"  Video ID: {result['video_id']}")
print(f"  Tipo: {result['video_type']}")
print(f"  Slides únicos: {result['slides']['num_unique_slides']}")
print(f"  Segmentos de transcripción: {len(result['transcript']['segments'])}")
print(f"  Desde cache: {result['from_cache']}")
print()

print("=" * 80)
print("EJEMPLO 2: Pipeline de Generación de Booklet (generate_booklet)")
print("=" * 80)
print()

# Este pipeline hace 4 pasos:
# PASO 1: Normalizar entrada (URL → video_id)
# PASO 2: Obtener transcripción (con cache)
# PASO 3: Obtener metadata (título, capítulos)
# PASO 4: Generar booklet
#   - Opción A: Por capítulos con contexto (recomendado)
#   - Opción B: Single-pass (más rápido, menos detallado)

print("Generando booklet...")
print(f"URL: {video_url}")
print()

# Ejecutar pipeline
result = generate_booklet(
    input_source=video_url,
    model="gpt-4o-mini",  # Modelo más barato para ejemplo
    provider="openai",
    temperature=0.5,
    use_chapters=True,  # Generación por capítulos
    parallel=False,  # Secuencial con contexto (recomendado)
    words_per_section=1000,  # Menos palabras para ejemplo
)

if result['success']:
    print("Resultado:")
    print(f"  Video: {result['video_title']}")
    print(f"  Secciones: {result.get('num_sections', 'N/A')}")
    print(f"  Longitud: {result['length']:,} caracteres")
    print(f"  Modelo: {result['model']}")
    print(f"  Desde cache: {result['from_cache']}")
    print()
    print("Preview del booklet (primeros 300 caracteres):")
    print("-" * 80)
    print(result['booklet'][:300])
    print("...")
else:
    print(f"Error: {result.get('error')}")

print()
print("=" * 80)
print("EJEMPLO 3: Flujo Secuencial con Contexto")
print("=" * 80)
print()

print("Cuando usas parallel=False, el pipeline:")
print()
print("Capítulo 1:")
print("  1. Genera contenido del capítulo 1")
print("  2. Extrae resumen: 'Conceptos: X, Y, Z'")
print("  3. Guarda resumen para contexto")
print()
print("Capítulo 2:")
print("  1. Recibe contexto: 'Ya cubrimos X, Y, Z'")
print("  2. Genera contenido del capítulo 2")
print("     - No repite explicaciones de X, Y, Z")
print("     - Usa terminología consistente")
print("     - Hace referencias al capítulo anterior")
print("  3. Extrae resumen: 'Conceptos previos: X, Y, Z. Nuevos: A, B'")
print("  4. Guarda resumen para contexto")
print()
print("Capítulo 3:")
print("  1. Recibe contexto: 'Ya cubrimos X, Y, Z, A, B'")
print("  2. Genera contenido del capítulo 3")
print("     - Construye sobre conceptos anteriores")
print("     - Mantiene coherencia narrativa")
print("  3. Y así sucesivamente...")
print()

print("=" * 80)
print("EJEMPLO 4: Control de Cache")
print("=" * 80)
print()

print("Primera ejecución:")
print("  generate_booklet(url)")
print("  → Obtiene transcript de YouTube")
print("  → Obtiene metadata")
print("  → Genera booklet")
print("  → Guarda todo en cache")
print()

print("Segunda ejecución (mismo video):")
print("  generate_booklet(url)")
print("  → Usa transcript del cache ✅")
print("  → Usa metadata del cache ✅")
print("  → Usa booklet del cache ✅")
print("  → Resultado instantáneo!")
print()

print("Regenerar solo el booklet:")
print("  generate_booklet(url, use_cached_booklet=False)")
print("  → Usa transcript del cache ✅")
print("  → Usa metadata del cache ✅")
print("  → Regenera booklet 🔄")
print("  → Útil para probar diferentes temperaturas/modelos")
print()

print("Regenerar todo:")
print("  generate_booklet(url,")
print("                   use_cached_transcript=False,")
print("                   use_cached_metadata=False,")
print("                   use_cached_booklet=False)")
print("  → Regenera todo desde cero 🔄")
print()

print("=" * 80)
print("EJEMPLO 5: Comparación Secuencial vs Paralelo")
print("=" * 80)
print()

print("MODO SECUENCIAL (parallel=False) - RECOMENDADO")
print("  Tiempo: ~10 minutos para video de 1 hora")
print("  Ventajas:")
print("    ✅ Terminología consistente")
print("    ✅ No repite explicaciones")
print("    ✅ Flujo narrativo coherente")
print("    ✅ Referencias entre capítulos")
print("  Desventajas:")
print("    ⏱️  Más lento (procesa uno por uno)")
print()

print("MODO PARALELO (parallel=True)")
print("  Tiempo: ~2 minutos para video de 1 hora")
print("  Ventajas:")
print("    ⚡ 5x más rápido")
print("    ⚡ Procesa todos los capítulos simultáneamente")
print("  Desventajas:")
print("    ❌ Sin contexto entre capítulos")
print("    ❌ Puede repetir conceptos")
print("    ❌ Terminología inconsistente")
print("    ❌ Sin referencias cruzadas")
print()

print("=" * 80)
print("FIN DE LOS EJEMPLOS")
print("=" * 80)
print()
print("Para ver el código completo de los pipelines:")
print("  - src/pipeline.py (funciones principales)")
print("  - src/processing/content/chapters.py (generación por capítulos)")
print("  - src/processing/video/youtube.py (obtención de datos)")
print()
print("Para documentación completa:")
print("  - PIPELINE_EXPLICACION.md")
print()
