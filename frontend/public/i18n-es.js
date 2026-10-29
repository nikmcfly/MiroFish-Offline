/*
 * Spanish UI layer for MiroFish-Offline / Capa de español para MiroFish-Offline.
 *
 * EN: UI strings are written in English inside the .vue components. Instead of editing every
 * component, this file translates the DOM as Vue renders it (MutationObserver). Strings that are
 * not in the dictionary are left untouched, so AI-generated content is never altered.
 * Active when the browser language is Spanish, or with ?lang=es (?lang=en switches it off; the
 * choice is remembered in localStorage). To add a string: exact entry in ES or a regex in PAT.
 *
 * ES: los textos de la interfaz están en inglés dentro de los .vue. En vez de tocar cada
 * componente, este fichero traduce el DOM a medida que Vue lo pinta. Lo que no está en el
 * diccionario no se toca, así que el contenido generado por la IA queda como sale.
 * Se activa si el navegador está en español o con ?lang=es (?lang=en lo desactiva y se recuerda).
 */
(function () {
  'use strict';
  var KEY = 'mirofish-lang', lang = null;
  try {
    var q = new URLSearchParams(location.search).get('lang');
    if (q === 'es' || q === 'en') localStorage.setItem(KEY, q);
    lang = localStorage.getItem(KEY);
  } catch (e) { /* storage blocked */ }
  if (!lang) lang = /^es\b/i.test(navigator.language || '') ? 'es' : 'en';
  // Mobile fix (also affects English): flex children without min-width overflow on narrow phones;
  // The hero title also needs to shrink ("Document" / "documento" overflow at 4.5rem).
  // Arreglo móvil: hijos flex sin min-width desbordan en móviles estrechos.
  var css = document.createElement('style');
  css.textContent = '@media (max-width:600px){.main-title{font-size:clamp(2rem,10.5vw,4.5rem)!important;letter-spacing:-1px!important;overflow-wrap:anywhere}.left-panel,.right-panel{min-width:0!important;max-width:100%!important}.left-panel *{overflow-wrap:anywhere}.metric-card{min-width:0!important;flex:1 1 0!important}}';
  document.head.appendChild(css);
  if (lang !== 'es') return;
  var ES = {
    // Portada
    'MIROFISH OFFLINE': 'MIROFISH OFFLINE',
    'Visit our Github': 'Ver en GitHub',
    'Offline Multi-Agent Simulation Engine': 'Motor de simulación multiagente local',
    'Upload Any Document': 'Sube cualquier documento',
    'Predict What Happens Next': 'Predice qué pasará después',
    'From a single document,': 'A partir de un solo documento,',
    'extracts reality seeds and builds a parallel world of': 'extrae semillas de realidad y construye un mundo paralelo de',
    'autonomous AI agents': 'agentes de IA autónomos',
    '— running entirely on your machine. Inject variables, observe emergent behavior, and find': '— todo en tu propio equipo. Introduce variables, observa los comportamientos emergentes y encuentra',
    '"local optima"': '«óptimos locales»',
    'in complex social dynamics.': 'en dinámicas sociales complejas.',
    'Your data never leaves your machine. The future is simulated locally': 'Tus datos no salen de tu equipo. El futuro se simula en local',
    'System Status': 'Estado del sistema',
    'Ready': 'Listo',
    'Local prediction engine on standby. Upload unstructured data to initialize a simulation.': 'Motor de predicción local en espera. Sube un documento para iniciar una simulación.',
    'Free': 'Gratis',
    'Runs on your hardware': 'Funciona en tu equipo',
    'Private': 'Privado',
    '100% offline, no cloud': '100 % local, sin nube',
    'Workflow Sequence': 'Flujo de trabajo',
    '01 / Reality Seeds': '01 / Semillas de realidad',
    'Supported: PDF, MD, TXT': 'Formatos: PDF, MD, TXT',
    'Drag & drop files here': 'Arrastra aquí los archivos',
    'or click to browse': 'o pulsa para elegirlos',
    'Parameters': 'Parámetros',
    '>_ 02 / Simulation Prompt': '>_ 02 / Pregunta de la simulación',
    '// Describe your simulation or prediction goal in natural language': '// Describe con tus palabras qué quieres simular o predecir',
    'Engine: Ollama + Neo4j (local)': 'Motor: Ollama + Neo4j (local)',
    'Start Engine': 'Arrancar motor',
    'Initializing...': 'Iniciando…',
    // Pasos
    'Step': 'Paso',
    'STEP 01': 'PASO 01',
    'Graph Build': 'Construcción del grafo',
    'Env Setup': 'Preparar entorno',
    'Simulation': 'Simulación',
    'Report': 'Informe',
    'Interaction': 'Interacción',
    'Extract reality seeds from your document, build knowledge graph with Neo4j + GraphRAG': 'Extrae las semillas de realidad del documento y construye el grafo de conocimiento con Neo4j + GraphRAG',
    'Generate agent personas, configure simulation parameters via local Ollama LLM': 'Genera los perfiles de los agentes y configura la simulación con la IA local (Ollama)',
    'Run multi-agent simulation locally with dynamic memory updates and emergent behavior': 'Ejecuta la simulación multiagente en local, con memoria que se actualiza y comportamientos emergentes',
    'ReportAgent analyzes the simulation results and generates a detailed prediction report': 'El agente del informe analiza los resultados y redacta un informe de predicción detallado',
    'Chat with any agent from the simulated world or discuss findings with ReportAgent': 'Habla con cualquier agente del mundo simulado o comenta las conclusiones con el agente del informe',
    'Graph': 'Grafo',
    'Split': 'Dividido',
    'Workbench': 'Mesa de trabajo',
    // Grafo
    'Live Knowledge Graph': 'Grafo de conocimiento en vivo',
    'Nodes': 'Nodos',
    'Edges': 'Relaciones',
    'Nodes:': 'Nodos:',
    'Edges:': 'Relaciones:',
    'Refresh Graph': 'Actualizar grafo',
    'Refresh graph': 'Actualizar grafo',
    'Refresh': 'Actualizar',
    'Real-time update in progress...': 'Actualizando en tiempo real…',
    'Name:': 'Nombre:',
    'UUID:': 'UUID:',
    'Created:': 'Creado:',
    'Properties:': 'Propiedades:',
    'Summary:': 'Resumen:',
    'Labels:': 'Etiquetas:',
    'Relationship': 'Relación',
    'Label:': 'Etiqueta:',
    'Type:': 'Tipo:',
    'Fact:': 'Hecho:',
    'Episodes:': 'Episodios:',
    'Valid From:': 'Válido desde:',
    'Invalid At:': 'Invalidado el:',
    'Expired At:': 'Caducado el:',
    'Loading graph data...': 'Cargando el grafo…',
    'Waiting for ontology generation': 'Esperando a que se genere la ontología',
    'Graph construction will start automatically after generation completes': 'El grafo se construirá solo en cuanto termine',
    'Building graph': 'Construyendo el grafo',
    'Data will be displayed soon...': 'Los datos aparecerán enseguida…',
    'Build Process': 'Proceso de construcción',
    'Ontology Generation': 'Generación de la ontología',
    'Description': 'Descripción',
    'After uploading documents, LLM analyzes the content and automatically generates an ontology structure suitable for knowledge graph simulation (entity types + relationship types)': 'Tras subir los documentos, la IA analiza el contenido y genera sola una ontología apta para simular con un grafo de conocimiento (tipos de entidad y de relación)',
    'Generation Progress': 'Progreso de la generación',
    'Generated Entity Types (': 'Tipos de entidad generados (',
    'Generated Relationship Types (': 'Tipos de relación generados (',
    'more relationships...': 'relaciones más…',
    'Waiting for ontology generation...': 'Esperando a la ontología…',
    'Based on the generated ontology, the documents are chunked and the Neo4j API is called to build the knowledge graph, extracting entities and relationships': 'Con la ontología generada, los documentos se trocean y se construye el grafo de conocimiento en Neo4j, extrayendo entidades y relaciones',
    'Waiting for ontology generation to complete...': 'Esperando a que termine la ontología…',
    'Build Progress': 'Progreso de la construcción',
    'Build Result': 'Resultado',
    'Entity Nodes': 'Nodos de entidad',
    'Relationship Edges': 'Relaciones',
    'Relation Edges': 'Relaciones',
    'Entity Types': 'Tipos de entidad',
    'SCHEMA Types': 'Tipos del esquema',
    'Build Complete': 'Construcción terminada',
    'Build Failed': 'Falló la construcción',
    'Ready for next step': 'Listo para el siguiente paso',
    'Enter Environment Setup': 'Ir a preparar el entorno',
    'Enter Environment Setup ➝': 'Ir a preparar el entorno ➝',
    'Project Information': 'Datos del proyecto',
    'Project Name': 'Nombre del proyecto',
    'Project ID': 'ID del proyecto',
    'Graph ID': 'ID del grafo',
    'Simulation Requirement': 'Pregunta de la simulación',
    'Graph Relationship Visualization': 'Visualización de relaciones del grafo',
    'Maximize/Restore': 'Maximizar/restaurar',
    'Some content is still being processed. It is recommended to manually refresh the graph later': 'Aún se está procesando contenido. Conviene actualizar el grafo dentro de un rato',
    'Close hint': 'Cerrar aviso',
    '- Self Relations': '- Relaciones consigo mismo',
    'items': 'elementos',
    'Show Edge Labels': 'Mostrar etiquetas de relación',
    'Fullscreen': 'Pantalla completa',
    'Exit Fullscreen': 'Salir de pantalla completa',
    'Node Details': 'Detalle del nodo',
    'No nodes to render': 'No hay nodos que mostrar',
    'Waiting for graph data...': 'Esperando datos del grafo…',
    'GraphRAG short-term/long-term memory updating in real-time': 'La memoria GraphRAG (corto y largo plazo) se actualiza en tiempo real',
    'Updating in real-time...': 'Actualizando en tiempo real…',
    'POST /api/graph/ontology/generate': 'POST /api/graph/ontology/generate',
    'LLM analyzes document content and simulation requirements, extracts reality seeds, and automatically generates appropriate ontology structures': 'La IA analiza el documento y la pregunta, extrae las semillas de realidad y genera la ontología adecuada',
    'ATTRIBUTES': 'ATRIBUTOS',
    'EXAMPLES': 'EJEMPLOS',
    'CONNECTIONS': 'CONEXIONES',
    'GENERATED ENTITY TYPES': 'TIPOS DE ENTIDAD GENERADOS',
    'GENERATED RELATION TYPES': 'TIPOS DE RELACIÓN GENERADOS',
    'GraphRAG Build': 'Construcción GraphRAG',
    'Based on the generated ontology, automatically chunk documents and invoke Neo4j to build knowledge graphs, extract entities and relationships, and form temporal memory and community summaries': 'Con la ontología, trocea los documentos y construye en Neo4j el grafo de conocimiento: extrae entidades y relaciones y forma la memoria temporal y los resúmenes de comunidad',
    'Graph build is complete. Please proceed to the next step to set up the simulation environment': 'El grafo está listo. Pasa al siguiente paso para preparar el entorno de simulación',
    // Historial
    'Simulation Records': 'Simulaciones anteriores',
    'Graph Construction': 'Construcción del grafo',
    'Environment Setup': 'Preparación del entorno',
    'Analysis Report': 'Informe de análisis',
    'files': 'archivos',
    'No Files': 'Sin archivos',
    'Loading...': 'Cargando…',
    'Associated Files': 'Archivos asociados',
    'No Associated Files': 'Sin archivos asociados',
    'Simulation Playback': 'Repetir simulación',
    'Step1': 'Paso 1',
    'Step2': 'Paso 2',
    'Step4': 'Paso 4',
    'Step3 "Start Simulation" and Step5 "Deep Interaction" must be launched during execution and do not support history playback': 'El paso 3 «Simulación» y el paso 5 «Interacción» solo funcionan en directo; no se pueden repetir desde el historial',
    'Completed': 'Terminado',
    'Generating': 'Generando',
    'Generating...': 'Generando…',
    'Waiting': 'En espera',
    'Waiting to start': 'Pendiente de empezar',
    'Complete': 'Terminado',
    'In Progress': 'En curso',
    'In progress': 'En curso',
    'Unnamed Simulation': 'Simulación sin nombre',
    'Not Started': 'Sin empezar',
    'Unknown File': 'Archivo desconocido',
    'Unknown': 'Desconocido',
    'Unknown error': 'Error desconocido',
    'None': 'Ninguno',
    // Paso 2
    'SYSTEM DASHBOARD': 'PANEL DEL SISTEMA',
    'Simulation Instance Initialization': 'Creación de la simulación',
    'Initialization': 'Inicio',
    'Create new simulation instance and fetch simulated world parameter template': 'Crea la simulación y obtiene la plantilla de parámetros del mundo simulado',
    'Simulation ID': 'ID de la simulación',
    'Task ID': 'ID de la tarea',
    'Generate Agent Personas': 'Generar los perfiles de los agentes',
    'Combined with context，Automatically invoke tools to organize entities and relationships from knowledge graph，Initialize simulation individuals，and give them unique behaviors and memories based on reality seed': 'Con el contexto, organiza las entidades y relaciones del grafo, crea los individuos de la simulación y les da comportamientos y recuerdos propios a partir de la semilla',
    'Current Agent Count': 'Agentes creados',
    'Expected Agent Total': 'Agentes previstos',
    'Current Related Topics Count for Reality Seed': 'Temas relacionados con la semilla',
    'Generated Agent Personas': 'Perfiles de agentes generados',
    'Generate Dual Platform Simulation Configuration': 'Configuración de las dos plataformas',
    'Generate Simulation Configuration': 'Generar la configuración',
    'LLM Based on simulation requirements and reality seed，Intelligently set world time flow rate、Recommendation algorithm、Active time period for each individual、Speech frequency、Event trigger and other parameters': 'A partir de la pregunta y la semilla, la IA fija el ritmo del tiempo, el algoritmo de recomendación, las horas activas de cada individuo, la frecuencia con que habla, los eventos y otros parámetros',
    'Simulation Duration': 'Duración simulada',
    'hours': 'horas',
    'Duration per round': 'Duración de cada ronda',
    'minutes': 'minutos',
    'Total rounds': 'Rondas en total',
    'rounds': 'rondas',
    'Active per hour': 'Activos por hora',
    'Peak period': 'Hora punta',
    'Working hours': 'Horario laboral',
    'Morning time period': 'Mañana',
    'Valley period': 'Hora valle',
    'Agent Configuration': 'Configuración de agentes',
    'Number': 'Número',
    'Agent': 'Agente',
    'Active period': 'Horas activas',
    'Post/time': 'Publicaciones/vez',
    'Comment/time': 'Comentarios/vez',
    'Response delay': 'Retardo de respuesta',
    'min': 'min',
    'Activity level': 'Nivel de actividad',
    'Sentiment tendency': 'Tendencia emocional',
    'Influence': 'Influencia',
    'Recommendation algorithm configuration': 'Algoritmo de recomendación',
    'Platform 1：Square / Information flow': 'Plataforma 1: Plaza / muro de noticias',
    'Platform 2：Topic / Community': 'Plataforma 2: Temas / comunidad',
    'Time weight': 'Peso de la novedad',
    'Popularity weight': 'Peso de la popularidad',
    'Relevance weight': 'Peso de la relevancia',
    'Virus threshold': 'Umbral de viralidad',
    'Echo chamber strength': 'Fuerza de la cámara de eco',
    'LLM Configuration inference': 'Razonamiento de la IA sobre la configuración',
    'Initial activation arrangement': 'Activación inicial',
    'Arranging': 'Preparando',
    'Based on narrative direction，Automatically generate initial activation events and trending topics，Guide the initial state of the simulated world': 'Según el hilo narrativo, genera los eventos de arranque y los temas del momento que marcan el estado inicial del mundo simulado',
    'Narrative Guidance Direction': 'Hilo narrativo',
    'Initial trending topics': 'Temas del momento al empezar',
    'Initial activation sequence (': 'Secuencia de arranque (',
    'Preparation completed': 'Preparación terminada',
    'Simulation environment preparation completed，Can start running simulation': 'El entorno está listo: ya se puede lanzar la simulación',
    'Simulation Rounds Setting': 'Rondas de la simulación',
    'MiroFish Automatically plan and infer reality': 'MiroFish planifica solo y simula',
    'hours，Each round represents reality': 'horas reales; cada ronda equivale a',
    'minutes time elapsed': 'minutos',
    'Custom': 'Personalizado',
    'IfAgentScale is100：Estimated time approximately': 'Con 100 agentes, tiempo estimado aproximado:',
    '40 (Recommendation)': '40 (recomendado)',
    'IfAgentScale is100：Estimated time': 'Con 100 agentes, tiempo estimado:',
    'If first run，Strongly recommend switching to‘Custom mode’Reduce simulation rounds，to quickly preview effects and reduce error risk ➝': 'Si es la primera vez, conviene pasar a «Personalizado» y poner pocas rondas para ver el resultado antes y con menos riesgo de error ➝',
    '← Return graph construction': '← Volver al grafo',
    'Start dual world parallel simulation ➝': 'Lanzar la simulación en los dos mundos ➝',
    'Age manifestation': 'Edad',
    'years old': 'años',
    'Gender manifestation': 'Género',
    'Country/Region': 'País/región',
    'Event manifestationMBTI': 'MBTI',
    'Persona Introduction': 'Presentación',
    'Reality Seed Related Topics': 'Temas relacionados con la semilla',
    'Detailed Persona Background': 'Trasfondo del personaje',
    'Event panoramic experience': 'Vivencia del suceso',
    'Complete behavior trajectory in this event': 'Todo lo que ha hecho en este suceso',
    'Behavior pattern profiling': 'Patrón de comportamiento',
    'Experience summary and action style preference': 'Resumen y estilo de actuación',
    'Unique memory imprints': 'Recuerdos propios',
    'Memory formed based on reality seed': 'Memoria formada a partir de la semilla',
    'Social Relationship Network': 'Red de relaciones',
    'Individual Links and Interaction Graph': 'Vínculos e interacciones del individuo',
    'Unknown Profession': 'Profesión desconocida',
    'Unknown profession': 'Profesión desconocida',
    'No introduction available': 'Sin presentación',
    'Male': 'Hombre',
    'Female': 'Mujer',
    'Other': 'Otro',
    'Creating...': 'Creando…',
    'Missing project or graph information': 'Faltan los datos del proyecto o del grafo',
    // Paso 3
    'Info Plaza': 'Plaza informativa',
    'Topic Community': 'Comunidad de temas',
    'ROUND': 'RONDA',
    'Elapsed Time': 'Tiempo transcurrido',
    'ACTS': 'ACCIONES',
    'Available Actions': 'Acciones disponibles',
    'POST': 'PUBLICAR',
    'LIKE': 'ME GUSTA',
    'REPOST': 'COMPARTIR',
    'QUOTE': 'CITAR',
    'FOLLOW': 'SEGUIR',
    'IDLE': 'INACTIVO',
    'COMMENT': 'COMENTAR',
    'DISLIKE': 'NO ME GUSTA',
    'SEARCH': 'BUSCAR',
    'TREND': 'TENDENCIAS',
    'MUTE': 'SILENCIAR',
    'REFRESH': 'ACTUALIZAR',
    'TOTAL EVENTS:': 'EVENTOS EN TOTAL:',
    'Reposted from @': 'Compartido de @',
    'Liked @': 'Le gustó a @',
    "'s post": ' (publicación)',
    'Reply to post #': 'Respuesta a la publicación #',
    'Search Query:': 'Búsqueda:',
    'Followed @': 'Sigue a @',
    'Post': 'Publicación',
    'Action Skipped': 'Acción omitida',
    'Waiting for agent actions...': 'Esperando a que actúen los agentes…',
    'SIMULATION MONITOR': 'MONITOR DE LA SIMULACIÓN',
    'Start Generating Report': 'Generar el informe',
    'Starting...': 'Arrancando…',
    'User': 'Usuario',
    'Upvoted': 'Votó a favor',
    'Downvoted': 'Votó en contra',
    // Paso 4
    'Prediction Report': 'Informe de predicción',
    'ID:': 'ID:',
    'Waiting for Report Agent...': 'Esperando al agente del informe…',
    'Sections': 'Secciones',
    'Elapsed': 'Transcurrido',
    'Tools': 'Herramientas',
    'Tools:': 'Herramientas:',
    'Enter Deep Interaction': 'Ir a la interacción',
    'Requirement': 'Pregunta',
    'sections planned': 'secciones previstas',
    'Iteration': 'Iteración',
    'Final:': 'Final:',
    'Section "': 'Sección «',
    '" content generated': '» redactada',
    'Report Generation Complete': 'Informe terminado',
    'Waiting for agent activity...': 'Esperando actividad de los agentes…',
    'CONSOLE OUTPUT': 'SALIDA DE CONSOLA',
    'Yes': 'Sí',
    'No': 'No',
    'Hide Params': 'Ocultar parámetros',
    'Show Params': 'Ver parámetros',
    'Structured View': 'Vista estructurada',
    'Raw Output': 'Salida en bruto',
    'Hide Response': 'Ocultar respuesta',
    'Show Response': 'Ver respuesta',
    'Deep Insight': 'Análisis profundo',
    'Panorama Search': 'Búsqueda panorámica',
    'Agent Interview': 'Entrevista a agentes',
    'Quick Search': 'Búsqueda rápida',
    'Graph Stats': 'Estadísticas del grafo',
    'Entity Query': 'Consulta de entidad',
    '(No response from this platform)': '(Sin respuesta en esta plataforma)',
    'Prediction Scenario:': 'Escenario de predicción:',
    'Latest Key Facts Associated in Sequential Memory': 'Últimos hechos clave de la memoria secuencial',
    'Collapse ▲': 'Contraer ▲',
    'Core Entities': 'Entidades principales',
    'Relationship Chains': 'Cadenas de relaciones',
    'Drift Query Generated Sub-questions': 'Subpreguntas generadas',
    'No current key memory': 'Sin memoria clave',
    'No core entities': 'Sin entidades principales',
    'No relationship chains': 'Sin cadenas de relaciones',
    'Current Active Memory': 'Memoria activa',
    'No current active memory': 'Sin memoria activa',
    'Historical Memory': 'Memoria histórica',
    'No historical memory': 'Sin memoria histórica',
    'Involved Entities': 'Entidades implicadas',
    'No involved entities': 'Sin entidades implicadas',
    'Selection Reason': 'Por qué se eligió',
    'No question available': 'Sin pregunta',
    'World 1': 'Mundo 1',
    'World 2': 'Mundo 2',
    'Show Less': 'Ver menos',
    'Show More': 'Ver más',
    'Key Quotes': 'Frases clave',
    'Interview Summary': 'Resumen de la entrevista',
    'Search:': 'Búsqueda:',
    'Search Results': 'Resultados',
    'No relevant results found': 'No hay resultados',
    'Related Relations': 'Relaciones relacionadas',
    'Related Nodes': 'Nodos relacionados',
    'Planning / Outline': 'Planificación / índice',
    'Report Started': 'Informe iniciado',
    'Plan Complete': 'Índice listo',
    'Section Start': 'Empieza la sección',
    'Content Ready': 'Contenido listo',
    'Section Done': 'Sección terminada',
    'Tool Call': 'Llamada a herramienta',
    'Tool Result': 'Resultado de herramienta',
    // Paso 5
    'Interactive Tools': 'Herramientas de interacción',
    'agents available': 'agentes disponibles',
    'Chat with Report Agent': 'Hablar con el agente del informe',
    'Select conversation target': 'Elige con quién hablar',
    'Send survey to the world': 'Encuesta al mundo simulado',
    'Report Agent - Chat': 'Agente del informe · chat',
    "Quick chat version of Report Agent with 4 professional tools, has MiroFish's full memory": 'Versión rápida del agente del informe, con 4 herramientas y toda la memoria de la simulación',
    'InsightForge Deep Attribution': 'InsightForge · análisis de causas',
    'Aligns real-world seed data with simulation environment state, combines Global/Local Memory mechanisms, provides cross-temporal deep attribution analysis': 'Cruza los datos reales de la semilla con el estado de la simulación y, con la memoria global y local, explica las causas a lo largo del tiempo',
    'PanoramaSearch Panoramic Tracking': 'PanoramaSearch · seguimiento completo',
    'Graph-based breadth-first traversal algorithm, reconstructs event propagation paths, captures full information flow topology': 'Recorre el grafo a lo ancho, reconstruye cómo se propagó cada suceso y muestra todo el flujo de información',
    'QuickSearch Fast Retrieval': 'QuickSearch · consulta rápida',
    'GraphRAG-based instant query interface, optimized indexing efficiency, for quickly extracting node attributes and discrete facts': 'Consulta instantánea sobre GraphRAG para sacar enseguida atributos de nodos y hechos concretos',
    'InterviewSubAgent Virtual Interview': 'InterviewSubAgent · entrevista virtual',
    'Autonomous interview, capable of parallel multi-turn conversations with individuals in simulated world, collects unstructured perspective data and psychological states': 'Entrevista a la vez a varios individuos del mundo simulado, en varias rondas, y recoge sus opiniones y su estado de ánimo',
    'Introduction': 'Presentación',
    'Type your question...': 'Escribe tu pregunta…',
    'Select survey targets': 'Elige a quién encuestar',
    'Selected': 'Seleccionados',
    'Select All': 'Todos',
    'Clear': 'Ninguno',
    'Survey Question': 'Pregunta de la encuesta',
    'Enter the question you want to ask all selected targets...': 'Escribe la pregunta para todos los seleccionados…',
    'Send Survey': 'Enviar encuesta',
    'Survey Results': 'Resultados de la encuesta',
    'replies': 'respuestas',
    'Chat with any individual': 'Habla con cualquier individuo',
    'Chat with Report Agent to deeply understand report content': 'Habla con el agente del informe para entenderlo a fondo',
    'Chat with simulated individuals to learn their perspectives': 'Habla con los individuos simulados para conocer su punto de vista',
    'You': 'Tú',
    'Report Agent': 'Agente del informe',
    'No response': 'Sin respuesta',
    'Request failed': 'Falló la petición',
    'Please select a simulated individual first': 'Elige antes un individuo simulado',
    'No response data': 'Sin datos de respuesta',
    // Mensajes de estado
    'Processing...': 'Procesando…',
    'Processing failed': 'Falló el procesado',
    'Project failed': 'El proyecto falló',
    'Failed to load project': 'No se pudo cargar el proyecto',
    'Building Graph': 'Construyendo el grafo',
    'Generating Ontology': 'Generando la ontología',
    'Uploading and analyzing docs...': 'Subiendo y analizando los documentos…',
    'Uploading files and analyzing documents...': 'Subiendo y analizando los documentos…',
    'Analyzing documents...': 'Analizando los documentos…',
    'Ontology generation failed': 'Falló la generación de la ontología',
    'Starting build...': 'Empezando la construcción…',
    'Starting graph build...': 'Empezando a construir el grafo…',
    'Graph build task started...': 'Construcción del grafo en marcha…',
    'Failed to start graph build': 'No se pudo empezar el grafo',
    'Build complete, loading graph...': 'Terminado, cargando el grafo…',
    'No files pending upload. Please go back to home and try again.': 'No hay archivos pendientes. Vuelve al inicio y prueba otra vez.',
    'Environment setup in development...': 'Preparación del entorno en desarrollo…',
    'Report generation request sent, please wait...': 'Informe solicitado, espera un momento…',
    'Start failed': 'No se pudo arrancar',
    'Async task completed': 'Tarea terminada'
  };

  // Textos con números o nombres dentro
  var PAT = [
    [/^Step (\d)\/(\d)$/, 'Paso $1/$2'],
    [/^Total (\d+) items$/, '$1 en total'],
    [/^Expand All (\d+) items ▼$/, 'Ver los $1 ▼'],
    [/^Self Relations \((\d+)\)$/, 'Relaciones consigo mismo ($1)'],
    [/^Current Key Memory \((\d+)\)$/, 'Memoria clave ($1)'],
    [/^Core Entities \((\d+)\)$/, 'Entidades principales ($1)'],
    [/^Relationship Chains \((\d+)\)$/, 'Cadenas de relaciones ($1)'],
    [/^Current Active Memory \((\d+)\)$/, 'Memoria activa ($1)'],
    [/^Historical Memory \((\d+)\)$/, 'Memoria histórica ($1)'],
    [/^Involved Entities \((\d+)\)$/, 'Entidades implicadas ($1)'],
    [/^Facts \((\d+)\)$/, 'Hechos ($1)'],
    [/^Relations \((\d+)\)$/, 'Relaciones ($1)'],
    [/^Nodes \((\d+)\)$/, 'Nodos ($1)'],
    [/^Agent (\d+)$/, 'Agente $1'],
    [/^Received (\d+) replies$/, '$1 respuestas recibidas'],
    [/^Sending survey to (\d+) targets\.\.\.$/, 'Enviando la encuesta a $1…'],
    [/^Loaded (\d+) simulated individuals$/, '$1 individuos simulados cargados'],
    [/^Selected conversation target: (.+)$/, 'Hablando con: $1'],
    [/^Sorry, an error occurred: (.+)$/, 'Lo siento, ha habido un error: $1'],
    [/^Send failed: (.+)$/, 'No se pudo enviar: $1'],
    [/^Graph data refreshed\. Nodes: (\d+), Edges: (\d+)$/, 'Grafo actualizado. Nodos: $1, relaciones: $2'],
    [/^Ontology generated successfully for project (.+)$/, 'Ontología generada para el proyecto $1'],
    [/^Graph build task started\. Task ID: (.+)$/, 'Grafo en construcción. Tarea: $1'],
    [/^Graph build failed: ?(.*)$/, 'Falló el grafo: $1'],
    [/^Project loaded\. Status: (.+)$/, 'Proyecto cargado. Estado: $1'],
    [/^Loading project (.+)\.\.\.$/, 'Cargando el proyecto $1…'],
    [/^Simulation instance created: (.+)$/, 'Simulación creada: $1'],
    [/^Preparation failed: (.+)$/, 'Falló la preparación: $1'],
    [/^Start simulation，Custom rounds: (\d+) rounds$/, 'Simulación en marcha, $1 rondas (personalizado)'],
    [/^Start simulation，Use auto-configured rounds: (\d+) rounds$/, 'Simulación en marcha, $1 rondas (automático)'],
    [/^Set max simulation rounds: (\d+)$/, 'Rondas máximas: $1'],
    [/^✓ Report generation task started: (.+)$/, '✓ Informe en marcha: $1'],
    [/^✗ Failed to start report generation: (.+)$/, '✗ No se pudo empezar el informe: $1'],
    [/^Loaded (\d+) NumberAgentPersona$/, '$1 perfiles de agente cargados'],
    [/^✓ All \(All\) (\d+) NumberAgentPersona generation completed$/, '✓ Generados los $1 perfiles de agente'],
    [/^FromNeo4jGraph read (\d+) entities$/, 'Leídas $1 entidades del grafo'],
    [/^Time Configuration: Per round(\d+)minutes, Total(\d+)rounds$/, 'Tiempo: $1 minutos por ronda, $2 rondas'],
    [/^Narrative Direction: (.+)$/, 'Hilo narrativo: $1'],
    [/^Failed to load (.+?): (.+)$/, 'No se pudo cargar ($1): $2']
  ];

  var SUELTOS = { 'Preparing simulation environment...': 'Preparando el entorno de simulación…', 'Preparation task started': 'Preparación en marcha', 'Start polling preparation progress...': 'Siguiendo el progreso de la preparación…', '✓ Preparation work completed': '✓ Preparación terminada', 'Start generationAgentPersona...': 'Generando los perfiles de agente…', '✓ Simulation configuration generation completed': '✓ Configuración generada', '✓ Env Setup Completed，Can start simulation': '✓ Entorno listo, ya puedes lanzar la simulación', 'Loading existing configuration data...': 'Cargando la configuración existente…', '✓ Simulation configuration loaded successfully': '✓ Configuración cargada', 'Configuration generating，Start polling wait...': 'Generando la configuración, esperando…', 'Detected existing completed preparation work，Use directly': 'La preparación ya estaba hecha: se reutiliza', 'Start generating dual platform simulation configuration...': 'Generando la configuración de las dos plataformas…', 'Prepare simulation script': 'Preparar el guion de la simulación', 'Starting dual-platform parallel simulation...': 'Lanzando la simulación en las dos plataformas…', 'Dynamic graph update mode enabled': 'Actualización dinámica del grafo activada', '✓ Cleaned old simulation logs and restarted simulation': '✓ Registros anteriores borrados y simulación reiniciada', '✓ Simulation engine started successfully': '✓ Motor de simulación en marcha', 'Stopping simulation...': 'Parando la simulación…', '✓ Detected all platform simulations have ended': '✓ Han terminado las simulaciones de las dos plataformas', 'Starting report generation...': 'Empezando el informe…', 'Report data loading completed': 'Informe cargado', 'Report Agent replied': 'El agente del informe ha respondido', 'Graph data loaded successfully': 'Grafo cargado', 'Graph data loaded successfully.': 'Grafo cargado.', '✅ Graph build complete, loading full data...': '✅ Grafo terminado, cargando todos los datos…', '✅ Graph load complete': '✅ Grafo cargado', 'Graph build task completed.': 'Construcción del grafo terminada.', 'Project view initialized.': 'Vista del proyecto lista.', 'Initiating graph build...': 'Empezando el grafo…', 'Started polling for graph data...': 'Siguiendo los datos del grafo…', 'Manual graph refresh triggered.': 'Actualización manual del grafo.', 'Graph polling stopped.': 'Seguimiento del grafo detenido.', 'Returning to Step 2, closing simulation...': 'Volviendo al paso 2, cerrando la simulación…', 'Closing simulation environment...': 'Cerrando el entorno de simulación…', '✓ Simulation environment closed': '✓ Entorno de simulación cerrado', 'Stopping simulation process...': 'Parando el proceso de simulación…', 'Entering Step 4: Report': 'Paso 4: informe', 'Entering Step 3: Simulation': 'Paso 3: simulación', 'Using auto-configured simulation rounds': 'Rondas automáticas', 'Graph auto-refresh started (30s)': 'Actualización automática del grafo (30 s)', 'Graph auto-refresh stopped': 'Actualización automática detenida', 'Starting ontology generation: Uploading files...': 'Generando la ontología: subiendo archivos…' };
  for (var k in SUELTOS) ES[k] = SUELTOS[k];


  // Mensajes de progreso del backend (salen tal cual en la interfaz)
  var BACK = { 'Chunking text...': 'Troceando el texto…', 'Data processing completed, getting graph information...': 'Datos procesados, leyendo el grafo…', 'Graph build completed': 'Grafo terminado', 'Initializing graph build service...': 'Iniciando la construcción del grafo…', 'Initializing Report Agent...': 'Iniciando el agente del informe…', 'Ontology set': 'Ontología fijada', 'Retrieving graph data...': 'Leyendo el grafo…', 'Setting ontology definition...': 'Fijando la ontología…', 'Start preparing simulation environment...': 'Preparando el entorno de simulación…', 'Starting graph building...': 'Empezando el grafo…', 'Task completed': 'Tarea terminada', 'Task failed': 'Tarea fallida', 'Text processing completed, generating graph data...': 'Texto procesado, generando el grafo…', 'Analyzing simulation requirements...': 'Analizando la pregunta…', 'Start planning report outline...': 'Planificando el índice del informe…', 'Outline planning completed': 'Índice terminado', 'Generating report outline...': 'Generando el índice del informe…', 'Parsing outline structure...': 'Analizando el índice…', 'Connecting to graph...': 'Conectando con el grafo…', 'Reading node data...': 'Leyendo los nodos…', 'Starting generation...': 'Empezando…', 'reportgeneratecomplete': 'Informe terminado', 'generatingassemblecompletereport...': 'Montando el informe completo…' };
  for (var b in BACK) ES[b] = BACK[b];
  // Prefijos de etapa del backend: «[2/4] GenerateAgentpersona: 1/6 - Completed 1/6: X»
  var ETAPAS = [
    [/Read knowledge graph entities/g, 'Leyendo entidades del grafo'],
    [/GenerateAgentpersona/g, 'Generando perfiles'],
    [/Generate ?[Ss]imulation ?[Cc]onfig(uration)?/g, 'Generando configuración'],
    [/Prepare ?[Ss]imulation ?[Ss]cript/g, 'Preparando el guion'],
    [/Completed (\d+)\/(\d+)/g, 'Hecho $1/$2'],
    [/Starting generation\.\.\./g, 'empezando…'],
    [/Reading node data\.\.\./g, 'leyendo nodos…'],
    [/Text split into (\d+) chunks/g, 'Texto dividido en $1 trozos'],
    [/Starting to add (\d+) text chunks\.\.\./g, 'Añadiendo $1 trozos de texto…'],
    [/Graph created: /g, 'Grafo creado: '],
    [/Build failed: /g, 'Falló la construcción: '],
    [/Batch (\d+) processing failed: /g, 'Falló el lote $1: ']
  ];
  function etapas(t) {
    if (!/^\[\d+\/\d+\] |^(Text split|Starting to add|Graph created|Build failed|Batch \d)/.test(t)) return null;
    var r = t;
    for (var i = 0; i < ETAPAS.length; i++) r = r.replace(ETAPAS[i][0], ETAPAS[i][1]);
    return r;
  }

  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, TEXTAREA: 1 };

  function tr(s) {
    var t = s.trim();
    if (!t || !/[A-Za-z]/.test(t)) return null;
    var r = ES.hasOwnProperty(t) ? ES[t] : null;
    if (r === null) {
      for (var i = 0; i < PAT.length; i++) {
        if (PAT[i][0].test(t)) { r = t.replace(PAT[i][0], PAT[i][1]); break; }
      }
    }
    if (r === null) r = etapas(t);
    if (r === null || r === t) return null;
    // conservar los espacios de alrededor (los nodos de texto de Vue los llevan)
    return s.replace(t, function () { return r; });
  }

  function texto(n) {
    var p = n.parentNode;
    if (!p || SKIP[p.nodeName] || (p.closest && p.closest('[data-no-es]'))) return;
    var r = tr(n.nodeValue);
    if (r !== null) n.nodeValue = r;
  }

  function elemento(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var v = el.getAttribute && el.getAttribute(ATTRS[i]);
      if (v) { var r = tr(v); if (r !== null) el.setAttribute(ATTRS[i], r); }
    }
  }

  function recorrer(root) {
    if (root.nodeType === 3) return texto(root);
    if (root.nodeType !== 1) return;
    elemento(root);
    if (SKIP[root.nodeName]) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) texto(n); else elemento(n); }
  }

  function arrancar() {
    recorrer(document.body);
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === 'characterData') texto(m.target);
        else if (m.type === 'attributes') elemento(m.target);
        else for (var j = 0; j < m.addedNodes.length; j++) recorrer(m.addedNodes[j]);
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  document.documentElement.lang = 'es';
  if (document.body) arrancar(); else document.addEventListener('DOMContentLoaded', arrancar);
})();
