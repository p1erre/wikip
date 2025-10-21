# Explicación de los Pipelines

## Arquitectura General

El sistema tiene **2 pipelines principales** en `src/pipeline.py`:

```
┌─────────────────────────────────────────────────────────┐
│                    src/pipeline.py                      │
│                                                         │
│  1. process_video()    - Procesa video completo        │
│  2. generate_booklet() - Genera contenido educativo    │
└─────────────────────────────────────────────────────────┘
```

---

## Pipeline 1: `process_video()` - Procesamiento Completo

### Flujo del Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ ENTRADA: URL de YouTube o archivo local                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 1: Normalizar entrada                                  │
│ • Extraer video_id de URL                                   │
│ • Determinar tipo (youtube/local)                           │
│ • Descargar video si es necesario                           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 2: Extracción de Slides                                │
│ • Verificar cache primero                                   │
│ • Si no está en cache:                                      │
│   - Extraer frames del video (2 FPS)                        │
│   - Detectar cambios de slides                              │
│   - Deduplicar slides únicos                                │
│   - Guardar en cache                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 3: Obtener Transcripción                               │
│ • Verificar cache primero                                   │
│ • Si no está en cache:                                      │
│   - Obtener de YouTube API                                  │
│   - Formatear segmentos con timestamps                      │
│   - Guardar en cache                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 4: Análisis Visual (Opcional)                          │
│ • Verificar cache primero                                   │
│ • Si no está en cache:                                      │
│   - Analizar cada slide con Vision LLM                      │
│   - Extraer texto, diagramas, conceptos                     │
│   - Guardar en cache                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ SALIDA: Dict con slides, transcript, vision_analysis        │
└──────────────────────────────────────────────────────────────┘
```

### Código Clave

```python
# Líneas 73-198 en src/pipeline.py

def process_video(input_source, force_reprocess=False, skip_vision=False):
    cache = get_cache(cache_dir)
    
    # 1. Normalizar entrada
    video_id, video_path, video_type = normalize_video_input(input_source)
    
    # 2. Extraer slides (con cache)
    slides = cache.get_slides(video_id) if not force_reprocess else None
    if not slides:
        slides = extract_slides_robust.func(
            video_path=video_path,
            fps_sample=2.0,
            build_policy="build_collapse"
        )
        cache.save_slides(video_id, slides)
    
    # 3. Obtener transcripción (con cache)
    transcript = cache.get_transcript(video_id) if not force_reprocess else None
    if not transcript:
        transcript_result = get_youtube_transcript.func(video_id)
        transcript = transcript_result['transcript']
        cache.save_transcript(video_id, transcript)
    
    # 4. Análisis visual (con cache, opcional)
    vision_analysis = None
    if not skip_vision:
        vision_analysis = cache.get_vision_analysis(video_id)
        if not vision_analysis:
            vision_analysis = analyze_slides_with_vision(
                slides_result=slides,
                transcript=transcript,
                provider=vision_provider
            )
            cache.save_vision_analysis(video_id, vision_analysis)
    
    return {
        'video_id': video_id,
        'slides': slides,
        'transcript': transcript,
        'vision_analysis': vision_analysis,
        'from_cache': {...}
    }
```

---

## Pipeline 2: `generate_booklet()` - Generación de Contenido

### Flujo del Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ ENTRADA: URL de YouTube                                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 1: Normalizar entrada                                  │
│ • Extraer video_id                                          │
│ • Validar que sea YouTube                                   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 2: Obtener Transcripción                               │
│ • Verificar cache (use_cached_transcript)                   │
│ • Si no está en cache:                                      │
│   - Obtener de YouTube API                                  │
│   - Guardar en cache                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 3: Obtener Metadata                                    │
│ • Verificar cache (use_cached_metadata)                     │
│ • Si no está en cache:                                      │
│   - Obtener título, duración, capítulos                     │
│   - Guardar en cache                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 4: Generar Booklet                                     │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Modo: Chapter-based (use_chapters=True)              │   │
│ │                                                       │   │
│ │ A. Obtener/Crear Capítulos                           │   │
│ │    • Usar capítulos del video si existen             │   │
│ │    • O crear semánticamente con LLM                  │   │
│ │                                                       │   │
│ │ B. Generar Secciones                                 │   │
│ │    ┌─────────────────────────────────────────────┐  │   │
│ │    │ Modo Secuencial (parallel=False) ✅         │  │   │
│ │    │ RECOMENDADO                                 │  │   │
│ │    │                                             │  │   │
│ │    │ Para cada capítulo:                         │  │   │
│ │    │ 1. Generar contenido (~2000 palabras)      │  │   │
│ │    │ 2. Extraer resumen del capítulo            │  │   │
│ │    │ 3. Pasar resumen como contexto al siguiente│  │   │
│ │    │                                             │  │   │
│ │    │ Beneficios:                                 │  │   │
│ │    │ • Terminología consistente                  │  │   │
│ │    │ • No repite explicaciones                   │  │   │
│ │    │ • Flujo narrativo coherente                 │  │   │
│ │    └─────────────────────────────────────────────┘  │   │
│ │                                                       │   │
│ │    ┌─────────────────────────────────────────────┐  │   │
│ │    │ Modo Paralelo (parallel=True) ⚡            │  │   │
│ │    │                                             │  │   │
│ │    │ Genera todos los capítulos simultáneamente │  │   │
│ │    │                                             │  │   │
│ │    │ Beneficios:                                 │  │   │
│ │    │ • 5x más rápido                             │  │   │
│ │    │                                             │  │   │
│ │    │ Desventajas:                                │  │   │
│ │    │ • Sin contexto entre capítulos              │  │   │
│ │    │ • Puede repetir conceptos                   │  │   │
│ │    │ • Terminología inconsistente                │  │   │
│ │    └─────────────────────────────────────────────┘  │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Modo: Single-pass (use_chapters=False)               │   │
│ │                                                       │   │
│ │ • Genera todo el contenido en una sola llamada LLM   │   │
│ │ • Más rápido pero menos detallado                    │   │
│ │ • Mejor para videos cortos (<15 min)                 │   │
│ └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PASO 5: Guardar en Cache                                    │
│ • Guardar booklet con clave: provider_model_mode            │
│ • Ejemplo: "openai_gpt-4o_chapters"                         │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ SALIDA: Dict con booklet (markdown), metadata, stats        │
└──────────────────────────────────────────────────────────────┘
```

### Código Clave - Generación Secuencial con Contexto

```python
# Líneas 784-821 en src/processing/content/chapters.py

def _generate_sections_sequential(chapters, transcript, ...):
    """Genera secciones secuencialmente con contexto de capítulos previos."""
    
    sections = []
    context_summaries = []  # Acumula resúmenes de capítulos previos
    
    for i, chapter in enumerate(chapters, 1):
        # 1. Construir contexto de capítulos anteriores
        previous_context = None
        if context_summaries:
            previous_context = "\n\n".join(context_summaries)
            logger.info(f"Using context from {len(context_summaries)} previous chapters")
        
        # 2. Generar contenido del capítulo actual
        chapter_transcript = extract_chapter_transcript(transcript, chapter)
        section = generate_section(
            chapter_title=chapter.get('title'),
            chapter_transcript=chapter_transcript,
            target_words=words_per_section,
            model=model,
            provider=provider,
            temperature=temperature,
            previous_context=previous_context,  # ← CONTEXTO AQUÍ
        )
        sections.append(section)
        
        # 3. Extraer resumen para el siguiente capítulo
        if section.get('success') and section.get('content'):
            summary = extract_chapter_summary(
                chapter_title=section['title'],
                chapter_content=section['content'],
                model="gpt-4o-mini",  # Modelo barato para resúmenes
                provider=provider
            )
            context_summaries.append(summary)  # ← GUARDAR PARA PRÓXIMO
    
    return sections
```

### Código Clave - Construcción del Prompt con Contexto

```python
# Líneas 546-599 en src/processing/content/chapters.py

def _build_section_prompt(chapter_title, transcript_text, target_words, 
                          previous_context=None):
    """Construye prompt con contexto opcional de capítulos previos."""
    
    # Sección de contexto si hay capítulos previos
    context_section = ""
    if previous_context:
        context_section = f"""PREVIOUS CHAPTERS CONTEXT:
The booklet has already covered the following topics. Use this context to:
- Reference concepts already defined (don't re-explain them)
- Maintain consistent terminology
- Build upon previous ideas
- Create natural transitions from earlier content

{previous_context}

---

"""
    
    return f"""You are writing a detailed section for an educational booklet.

SECTION TITLE: {chapter_title}

{context_section}TRANSCRIPT FOR THIS SECTION:
{transcript_text}

YOUR TASK:
Write a comprehensive, detailed section about this topic.

REQUIREMENTS:
1. LENGTH: Target {target_words} words
2. CONTENT: Cover ALL points from transcript
3. STYLE: Clear, educational, detailed
4. CONTEXT: Use previous chapters' context to maintain consistency
...
"""
```

---

## Sistema de Cache

### Estructura del Cache

```
.cache/
└── videos/
    └── VIDEO_ID/
        ├── metadata.json           # Título, duración, capítulos
        ├── transcript.json         # Segmentos con timestamps
        ├── slides/
        │   ├── slides_metadata.json
        │   └── slide_*.jpg
        ├── vision_analysis.json    # Análisis de slides
        └── booklets/
            ├── openai_gpt-4o_chapters.json
            ├── openai_gpt-4o-mini_chapters.json
            └── anthropic_claude-3-5-sonnet_chapters.json
```

### Control de Cache

```python
# Control granular en generate_booklet()

result = generate_booklet(
    video_url,
    use_cached_transcript=True,   # Usar transcripción cacheada
    use_cached_metadata=True,     # Usar metadata cacheada
    use_cached_booklet=False,     # Regenerar booklet (nuevo contenido)
)
```

**Casos de uso:**

1. **Primera ejecución**: Todo se genera y cachea
2. **Iterar en contenido**: Mantener transcript/metadata, regenerar booklet
3. **Cambiar modelo**: Mantener transcript/metadata, nuevo booklet con otro modelo
4. **Forzar todo**: `use_cached_*=False` para regenerar todo

---

## Módulos de Procesamiento

### 1. `src/processing/video/youtube.py`

**Funciones:**
- `get_youtube_transcript()` - Obtiene transcripción de YouTube
- `get_video_metadata()` - Obtiene título, duración, capítulos
- `download_youtube_content()` - Descarga video/audio

### 2. `src/processing/slides/extraction.py`

**Funciones:**
- `extract_slides_robust()` - Extrae slides únicos del video
  - Detecta cambios de slides
  - Deduplicación global
  - Detección de "progressive reveal"

### 3. `src/processing/vision/analyzer.py`

**Funciones:**
- `analyze_slides_with_vision()` - Analiza slides con Vision LLM
  - Soporta Gemini, GPT-4V, OpenRouter
  - Extrae texto, diagramas, conceptos clave

### 4. `src/processing/content/chapters.py`

**Funciones:**
- `generate_booklet_by_chapters()` - Genera booklet por capítulos
- `create_chapters()` - Crea capítulos semánticamente
- `generate_section()` - Genera una sección con contexto
- `extract_chapter_summary()` - Extrae resumen para contexto

### 5. `src/processing/content/generation.py`

**Funciones:**
- `generate_booklet_from_transcript()` - Generación single-pass
- `format_transcript_for_llm()` - Formatea transcripción para LLM

---

## Ejemplo de Uso Completo

```python
from src.pipeline import generate_booklet

# Generar booklet con contexto secuencial (recomendado)
result = generate_booklet(
    input_source="https://youtube.com/watch?v=VIDEO_ID",
    model="gpt-4o",
    provider="openai",
    temperature=0.5,
    use_chapters=True,      # Generación por capítulos
    parallel=False,         # Secuencial con contexto
    words_per_section=2000, # ~2000 palabras por capítulo
)

if result['success']:
    print(f"Video: {result['video_title']}")
    print(f"Secciones: {result['num_sections']}")
    print(f"Longitud: {result['length']} caracteres")
    print(f"Desde cache: {result['from_cache']}")
    
    # Guardar booklet
    with open('booklet.md', 'w') as f:
        f.write(result['booklet'])
```

---

## Ventajas del Sistema

1. **Cache Inteligente**: Evita reprocesar datos costosos
2. **Contexto Secuencial**: Mantiene coherencia entre capítulos
3. **Flexible**: Soporta múltiples proveedores y modelos
4. **Granular**: Control fino sobre qué cachear y regenerar
5. **Escalable**: Modo paralelo para velocidad cuando no se necesita contexto

---

## Flujo de Datos Completo

```
YouTube URL
    ↓
[normalize_video_input] → video_id
    ↓
[get_youtube_transcript] → transcript (segments con timestamps)
    ↓
[get_video_metadata] → metadata (título, capítulos)
    ↓
[create_chapters] → chapters (semánticos o del video)
    ↓
Para cada chapter:
    [extract_chapter_transcript] → chapter_transcript
    ↓
    [generate_section con previous_context] → section_content
    ↓
    [extract_chapter_summary] → summary
    ↓
    summary → previous_context para siguiente chapter
    ↓
[combine_sections] → booklet completo (markdown)
    ↓
Guardar en cache
    ↓
Retornar resultado
```

---

## Resumen

- **2 pipelines principales**: `process_video()` y `generate_booklet()`
- **Cache en 3 niveles**: transcript, metadata, booklet
- **Generación secuencial con contexto**: Mantiene coherencia
- **Modo paralelo opcional**: 5x más rápido sin contexto
- **Flexible**: Múltiples proveedores LLM y modelos
