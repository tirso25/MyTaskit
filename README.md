# 📋 MyTaskit - Gestor de Tareas para Terminal

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Textual](https://img.shields.io/badge/Textual-0.47+-purple.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)

Una aplicación de gestión de tareas moderna y completa para la terminal, construida con [Textual](https://textual.textualize.io/).

[Características](#-características) • [Instalación](#-instalación) • [Uso](#-uso) • [Atajos de Teclado](#%EF%B8%8F-atajos-de-teclado)

</div>

---

## ✨ Características

### 🎯 Gestión Completa de Tareas y Subtareas
- **Crear, editar y eliminar** tareas y subtareas con interfaz intuitiva
- **Sistema de Estado de 3 Vías**: Control completo para tareas y subtareas en estados `🔄 En progreso`, `⏳ En espera` y `✅ Completado`
- **Organización Visual por Secciones**: Listas organizadas limpiamente en tres bloques dinámicos:
  - `── En progreso ──`
  - `── En espera ──`
  - `── Completadas ──`
- **Sincronización Inteligente**: Al alternar finalización (`Espacio` / `Enter`), la tarea/subtarea conmuta de forma coherente entre `En progreso` y `Completado`, preservando el estado `En espera` cuando aplica.
- **Vista General unificada**: Completa (`Espacio`/`Enter`), edita (`e`) y elimina (`d`) tareas y subtareas desde una sola vista
- **Prioridades** con 4 niveles: Sin prioridad, Baja ⬇, Media ■, Alta ⬆
- **Fechas de vencimiento** con calendario visual integrado
- **Comentarios** con soporte para enlaces/URLs
- **Etiquetas** personalizables e ilimitadas por tarea/subtarea
- **Auto-guardado** cada 10 segundos (silencioso)

### 🕒 Reloj Inamovible & Modal de Herramientas de Tiempo (`Ctrl+T`)
- **Reloj Superior Inamovible**: Muestra la fecha y hora en tiempo real con formato `dd/mm/yyyy HH:MM:SS` fijo en la esquina superior derecha, inmune al desplazamiento horizontal de pestañas cuando se crean múltiples grupos.
- **Modal de Herramientas de Tiempo**: Acceso inmediato presionando `Ctrl+T` en cualquier momento.
- **Navegación por Pestañas Horizontales**: Cambio de grupo/modo con las flechas (`←` / `→` o `h` / `l`):
  - ⏱️ **Cronómetro**: Medición de tiempo transcurrido en dígitos ASCII (`Espacio` Iniciar/Pausar, `R` Reiniciar).
  - 🍅 **Pomodoro**: Ciclos de enfoque/descanso personalizables (`S` Configurar, `Espacio` Iniciar/Pausar, `R` Reiniciar).
  - ⏲️ **Temporizador**: Cuenta regresiva con nombre de actividad y alerta/notificación al finalizar (`S` Configurar, `Espacio` Iniciar/Pausar, `R` Reiniciar).
  - 🕐 **Reloj Digital**: Reloj digital en arte ASCII con fecha completa en español.
- **Ejecución en Segundo Plano** ⭐ NUEVO: Al pulsar `Esc` la ventana se oculta pero los temporizadores **siguen corriendo en segundo plano**. Las notificaciones de Pomodoro y Temporizador se reciben incluso con la ventana cerrada. Al volver a abrir con `Ctrl+T` el estado se mantiene intacto.
- **Cierre Completo con `Q`**: Al pulsar `Q` se **detienen y reinician** todos los temporizadores y se cierra la ventana por completo.

### 📝 Notas, 🎨 Pizarras y 🎤 Notas de Voz
- **Notas**: Almacena notas de texto globales o integradas en tareas y subtareas
- **Pizarras**: Dibujos y esquemas visuales vinculados o independientes
- **Audios**: Grabación y reproducción de notas de voz integradas
- **Pestañas dedicadas**: Acceso rápido en la barra superior para Subtareas, Notas, Pizarras, Audios y Etiquetas

### 🐍 Minijuego Snake Infinito
- **Activación rápida**: Presiona `Ctrl+G` en cualquier momento para jugar
- **Controles**: Flechas, WASD o HJKL para moverte
- **Pantalla de Game Over**: Muestra la puntuación final alcanzada y el tiempo aguantado (`MM:SS`)
- **Salida directa**: Presiona `Ctrl+F` o `Esc` para volver a la aplicación

### 📁 Organización por Grupos
- **Grupos personalizados** para categorizar tareas
- **Grupo General** - Vista unificada de todas las tareas, subtareas, notas, pizarras y audios
- **Grupo Sin grupo** - Tareas sin categoría asignada
- **Navegación rápida** entre grupos con flechas, H/L o Tab
- **Gestión de grupos**: crear, renombrar y eliminar

### 🔍 Filtrado y Ordenación Avanzada
- **Filtros múltiples** combinables:
  - 📅 Por fechas (múltiples fechas o sin fecha)
  - 🏷️ Por etiquetas (modo AND - todas deben coincidir)
  - ✅ Por estado (`🔄 En progreso`, `⏳ En espera`, `✅ Completadas`)
  - ⭐ Por prioridad (múltiples niveles)
- **Título de Filtro Adaptativo**: Al presionar `f` en vistas o modales de subtareas, el modal se personaliza dinámicamente como `🔍 Filtrar Subtareas`
- **Navegación por Teclado Instantánea**: Selector de estado (`StatusPickerModal`) ultra-fluido sin pestañeos visuales

- **Ordenación flexible** por categorías:
  - 🔤 Alfabético (A→Z o Z→A)
  - 📅 Fecha (próximas primero o lejanas primero)
  - ⭐ Prioridad (alta→baja o baja→alta)
  - ➕ **Combinable**: Los criterios se aplican en orden jerárquico respetando las secciones de estado

### 📅 Modo Calendario
- **Calendario visual** completo
- **Navegación** por días, semanas y meses
- **Indicadores visuales** de días con tareas
- **Vista de tareas del día** seleccionado
- **Salto rápido** al grupo de una tarea
- **Asignación masiva** de fechas a tareas sin fecha

### 💬 Comentarios con Enlaces
- **Comentarios ilimitados** por tarea y subtarea
- **Enlaces/URLs** opcionales en cada comentario
- **Apertura automática** de enlaces en navegador con Control + o
- **Icono 🔗** indica comentarios con enlaces

### 🔔 Sistema de Recordatorios
- **Notificaciones** automáticas al iniciar la app
- **Alerta** de tareas que vencen HOY
- **Modal no intrusivo** con información del grupo

### 🎨 Interfaz Moderna
- **Tema Dracula** por defecto
- **Diseño responsive** que se adapta a tu terminal
- **Navegación tipo Vim** (h/j/k/l) además de flechas
- **Estadísticas en tiempo real** en barra inferior
- **Separación visual clara** entre estados *En progreso*, *En espera* y *Completadas*

### 🔎 Búsqueda Global
- **Búsqueda de texto** en todas las tareas, subtareas y notas
- **Navegación directa** al grupo de la tarea encontrada
- **Resultados múltiples** con modal de selección

---

## 🔄 Sistema de Deshacer/Rehacer

MyTaskit incluye un potente sistema de **undo/redo** que te permite deshacer y rehacer cualquier acción:

### Características
- ⏮️ **Deshacer** con `Ctrl+Z` - Revierte la última acción realizada
- ⏭️ **Rehacer** con `Ctrl+Y` - Restaura una acción que fue deshecha
- 📚 **Hasta 50 niveles** - Mantiene un historial de hasta 50 acciones
- 🎯 **Restauración completa** - Recupera el estado exacto anterior (tareas, subtareas, estados, grupos, etiquetas, selección actual)
- 🔄 **Inteligente** - La pila de rehacer se limpia automáticamente al realizar una nueva acción

### ¿Qué se puede deshacer?
✅ Crear, editar y eliminar **tareas y subtareas**  
✅ Cambiar el **estado de 3 vías** (En progreso / En espera / Completado)  
✅ Crear, renombrar y eliminar **grupos** (junto con sus tareas)  
✅ Crear, editar y eliminar **etiquetas**  
✅ Marcar/desmarcar tareas como **completadas**  
✅ Asignar **fechas** desde el calendario  
✅ Cambios en **comentarios** y **prioridades**  

---

## 🚀 Instalación

### Requisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Instalación Rápida
```bash
# Clonar el repositorio
git clone https://github.com/tirso25/MyTaskit.git
cd MyTaskit

# Instalar dependencias
pip install textual

# Ejecutar la aplicación
python MyTaskit.py
```

---

## 📖 Uso

### Inicio Rápido

1. **Ejecutar la aplicación**:
```bash
   python MyTaskit.py
```

2. **Crear tu primera tarea**:
   - Presiona `a` para añadir una tarea
   - Escribe el texto y presiona Enter

3. **Herramientas de Tiempo**:
   - Presiona `Ctrl+T` para abrir la ventana de Reloj/Cronómetro/Pomodoro/Temporizador.
   - Usa `←` / `→` o `h` / `l` para navegar entre herramientas.

4. **Marcar como completada**:
   - Selecciona una tarea con `↑` `↓`
   - Presiona `Espacio` o `Enter`

---

## ⌨️ Atajos de Teclado

### Gestión de Tareas y Subtareas
| Tecla | Acción |
|-------|--------|
| `a` | Añadir nueva tarea / subtarea |
| `e` | Editar tarea o subtarea seleccionada (incluye cambio de estado) |
| `d` | Eliminar tarea o subtarea seleccionada |
| `Espacio` | Marcar/Desmarcar como completada (Conmuta estado a Completado / En progreso) |
| `Enter` | Marcar/Desmarcar como completada |

### Herramientas de Tiempo
| Tecla | Acción |
|-------|--------|
| `Ctrl+T` | Abrir/cerrar modal de Reloj, Cronómetro, Pomodoro y Temporizador |
| `←` / `→` o `h` / `l` | Cambiar de grupo/herramienta de tiempo en el modal |
| `Espacio` | Iniciar / Pausar (Cronómetro / Pomodoro / Temporizador) |
| `R` | Reiniciar tiempo |
| `S` | Configurar tiempos (Pomodoro / Temporizador) |
| `Esc` | **Ocultar** modal (los temporizadores siguen corriendo en segundo plano) |
| `Q` | **Cerrar y apagar** (detiene y reinicia todos los temporizadores) |

### Deshacer/Rehacer
| Tecla | Acción |
|-------|--------|
| `Ctrl+Z` | Deshacer última acción (hasta 50 acciones) |
| `Ctrl+Y` | Rehacer acción deshecha |

### Navegación
| Tecla | Acción |
|-------|--------|
| `↑` `↓` o `k` `j` | Navegar entre tareas y subtareas |
| `←` `→` o `h` `l` | Cambiar de grupo |
| `Tab` | Ciclo: General → Sin grupo → Grupos personalizados → Pestañas especiales |

### Grupos
| Tecla | Acción |
|-------|--------|
| `g` | Crear nuevo grupo |
| `G` | Opciones de grupo (renombrar/eliminar) |

### Filtros y Ordenación
| Tecla | Acción |
|-------|--------|
| `f` | Abrir modal de filtros (Muestra `Filtrar Subtareas` o `Filtrar Tareas` según contexto) |
| `F5` | Resetear todos los filtros |
| `o` | Abrir modal de ordenación |
| `/` | Buscar tareas y subtareas por texto |

### Minijuego Snake 🐍
| Tecla | Acción |
|-------|--------|
| `Ctrl+G` | Abrir minijuego de Snake |
| `Flechas` / `WASD` / `HJKL` | Mover la serpiente |
| `R` / `Enter` | Reiniciar partida tras Game Over |
| `Ctrl+F` / `Esc` | Salir del juego |

---

## 🖼️ Capturas / Esquemas de Pantalla

### Vista Principal con Reloj Inamovible y Secciones
```
┌─ 📋 TODO App ─────────────────────────────────────────────────────────────┐
│  📚 General   📋 Sin grupo   📁 Trabajo    │ 🕒 25/07/2026 15:35:00       │
├────────────────────────────────────────────┴──────────────────────────────┤
│                             ── En progreso ──                             │
│ ☐ ⬆  Revisar propuesta cliente 🔄 En progreso  Urgente 💬2 🔗1  📅 08/01  │
│                             ── En espera ──                               │
│ ☐ ■  Esperar feedback diseño   ⏳ En espera    Trabajo  💬1     📅 12/01  │
│                             ── Completadas ──                             │
│ ☑    Llamar al dentista        ✅ Completado   Personal                   │
├───────────────────────────────────────────────────────────────────────────┤
│ Total: 3 | En progreso: 1 | En espera: 1 | Completadas: 1 | Grupo: General │
└───────────────────────────────────────────────────────────────────────────┘
```

### Modal de Herramientas de Tiempo (`Ctrl+T`)
```
┌─ 🕐 Herramientas de Tiempo ──────────────────────────────────────────┐
│  [⏱️ Cronómetro]  [🍅 Pomodoro]  [⏲️ Temporizador]  [🕐 Reloj]       │
│                                                                      │
│   ██████  ██████     ██████  ██████     ██████  ██████               │
│   █    █  █    █        █    █    █     █    █  █    █               │
│   █    █  █    █     ████    ████       █    █  █    █               │
│   █    █  █    █     █          █       █    █  █    █               │
│   ██████  ██████     ██████  ██████     ██████  ██████               │
│                                                                      │
│   🍅 Pomodoro - Estado: 🎯 FOCUS                                     │
│   ▶️ En marcha                                                       │
│                                                                      │
│   ←/→: Cambiar | Espacio: Pausar | R: Reset | S: Config             │
│   Esc: Ocultar (sigue corriendo) | Q: Apagar                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 👤 Autor

**Tirso**

- GitHub: [@tirso](https://github.com/tirso25)

<div align="center">

**¿Te gusta este proyecto? ¡Dale una ⭐ en GitHub!**

</div>
