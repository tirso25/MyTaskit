#!/usr/bin/env python3
"""
TODO App - Aplicación de tareas para terminal con grupos
Controles:
  a - Añadir tarea
  e - Editar tarea seleccionada
  d - Eliminar tarea seleccionada
  g - Crear nuevo grupo
  G - Editar/Eliminar grupo actual
  ←/→ - Cambiar entre grupos
  Espacio/Enter - Marcar/desmarcar como completada
  q - Salir
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual.binding import Binding
from textual import on
from dataclasses import dataclass
from typing import Optional
import json
from pathlib import Path
from datetime import datetime


@dataclass
class Task:
    """Representa una tarea."""
    id: int
    text: str
    done: bool = False
    created_at: str = ""
    group_id: Optional[int] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m %H:%M")


@dataclass
class Group:
    """Representa un grupo de tareas."""
    id: int
    name: str


class TaskWidget(Static):
    """Widget que representa una tarea individual."""
    
    DEFAULT_CSS = """
    TaskWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    
    TaskWidget:hover {
        background: $boost;
    }
    
    TaskWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    
    TaskWidget .checkbox {
        width: 4;
        height: 1;
    }
    
    TaskWidget .task-text {
        width: 1fr;
        height: 1;
    }
    
    TaskWidget .task-time {
        width: 12;
        height: 1;
        text-align: right;
        color: $text-muted;
    }
    
    TaskWidget.done .task-text {
        text-style: strike;
        color: $text-muted;
    }
    
    TaskWidget.done .checkbox {
        color: $success;
    }
    """
    
    def __init__(self, task_data: Task, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_data = task_data
        self._selected = False
    
    def compose(self) -> ComposeResult:
        checkbox = "☑" if self.task_data.done else "☐"
        yield Label(checkbox, classes="checkbox")
        yield Label(self.task_data.text, classes="task-text")
        yield Label(self.task_data.created_at, classes="task-time")
    
    @property
    def selected(self) -> bool:
        return self._selected
    
    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        if value:
            self.add_class("selected")
        else:
            self.remove_class("selected")
    
    def toggle_done(self) -> None:
        """Alterna el estado de completado."""
        self.task_data.done = not self.task_data.done
        if self.task_data.done:
            self.add_class("done")
        else:
            self.remove_class("done")
        checkbox = self.query_one(".checkbox", Label)
        checkbox.update("☑" if self.task_data.done else "☐")
    
    def update_text(self, new_text: str) -> None:
        """Actualiza el texto de la tarea."""
        self.task_data.text = new_text
        text_label = self.query_one(".task-text", Label)
        text_label.update(new_text)
    
    def on_mount(self) -> None:
        if self.task_data.done:
            self.add_class("done")


class InputModal(ModalScreen[Optional[str]]):
    """Modal genérico para input de texto."""
    
    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    
    InputModal > Container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    InputModal .modal-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    
    InputModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    
    InputModal .button-row {
        width: 100%;
        height: auto;
        align: center middle;
    }
    
    InputModal Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]
    
    def __init__(self, title: str = "Input", initial_text: str = "", placeholder: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self.initial_text = initial_text
        self.placeholder_text = placeholder
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.title_text, classes="modal-title")
            yield Input(value=self.initial_text, placeholder=self.placeholder_text, id="modal-input")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()
    
    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        input_widget = self.query_one("#modal-input", Input)
        text = input_widget.value.strip()
        self.dismiss(text if text else None)
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        self.on_save()
    
    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """Modal de confirmación."""
    
    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    
    ConfirmModal > Container {
        width: 50;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    
    ConfirmModal .modal-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    
    ConfirmModal .button-row {
        width: 100%;
        height: auto;
        align: center middle;
    }
    
    ConfirmModal Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]
    
    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.message = message
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.message, classes="modal-title")
            with Horizontal(classes="button-row"):
                yield Button("Sí", variant="error", id="yes")
                yield Button("No", variant="default", id="no")
    
    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)
    
    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)
    
    def action_cancel(self) -> None:
        self.dismiss(False)


class GroupOptionsModal(ModalScreen[str]):
    """Modal para opciones de grupo (editar/eliminar)."""
    
    DEFAULT_CSS = """
    GroupOptionsModal {
        align: center middle;
    }
    
    GroupOptionsModal > Container {
        width: 40;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    GroupOptionsModal .modal-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    
    GroupOptionsModal Button {
        width: 100%;
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]
    
    def __init__(self, group_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.group_name = group_name
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Grupo: {self.group_name}", classes="modal-title")
            yield Button("✏️  Renombrar", variant="primary", id="rename")
            yield Button("🗑️  Eliminar grupo y tareas", variant="error", id="delete")
            yield Button("Cancelar", variant="default", id="cancel")
    
    @on(Button.Pressed, "#rename")
    def on_rename(self) -> None:
        self.dismiss("rename")
    
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.dismiss("delete")
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss("")
    
    def action_cancel(self) -> None:
        self.dismiss("")


class SearchResultItem(Static):
    """Widget para un resultado de búsqueda."""
    
    DEFAULT_CSS = """
    SearchResultItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    
    SearchResultItem:hover {
        background: $boost;
    }
    
    SearchResultItem.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    
    SearchResultItem .result-task {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }
    
    SearchResultItem .result-group {
        width: auto;
        height: 1;
        content-align: right middle;
        color: $text-muted;
    }
    """
    
    def __init__(self, task_data: Task, group_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_data = task_data
        self.group_name = group_name
        self._selected = False
    
    def compose(self) -> ComposeResult:
        yield Static(self.task_data.text, classes="result-task")
        yield Static(f"Grupo: {self.group_name}", classes="result-group")
    
    @property
    def selected(self) -> bool:
        return self._selected
    
    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        if value:
            self.add_class("selected")
        else:
            self.remove_class("selected")


class SearchResultsScreen(ModalScreen[Optional[Task]]):
    """Pantalla de resultados de búsqueda."""
    
    DEFAULT_CSS = """
    SearchResultsScreen {
        align: center middle;
    }
    
    SearchResultsScreen > Container {
        width: 70;
        height: 20;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    SearchResultsScreen .modal-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    
    SearchResultsScreen #results-list {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    
    SearchResultsScreen .hint {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
        Binding("up", "move_up", "Arriba", show=False),
        Binding("down", "move_down", "Abajo", show=False),
        Binding("enter", "select_result", "Ir al grupo", show=False),
    ]
    
    def __init__(self, results: list[tuple[Task, str]], search_term: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.results = results  # Lista de (Task, group_name)
        self.search_term = search_term
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"🔍 Resultados para '{self.search_term}'", classes="modal-title")
            yield Container(id="results-list")
            yield Label("↑↓ Navegar | Enter: Ir al grupo | Esc: Cerrar", classes="hint")
    
    async def on_mount(self) -> None:
        results_list = self.query_one("#results-list", Container)
        for i, (task, group_name) in enumerate(self.results):
            item = SearchResultItem(task, group_name, id=f"result-{i}")
            await results_list.mount(item)
            if i == 0:
                item.selected = True
    
    def update_selection(self) -> None:
        for i in range(len(self.results)):
            try:
                item = self.query_one(f"#result-{i}", SearchResultItem)
                item.selected = (i == self.selected_index)
            except Exception:
                pass
    
    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.selected_index < len(self.results) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_select_result(self) -> None:
        if self.results:
            task, _ = self.results[self.selected_index]
            self.dismiss(task)
    
    def action_cancel(self) -> None:
        self.dismiss(None)


class GroupTab(Static):
    """Widget para una pestaña de grupo."""
    
    DEFAULT_CSS = """
    GroupTab {
        width: auto;
        height: 3;
        padding: 0 2;
        margin: 0 1;
        border: solid $primary-background;
        content-align: center middle;
    }
    
    GroupTab:hover {
        background: $boost;
    }
    
    GroupTab.active {
        border: solid $accent;
        background: $accent 20%;
        text-style: bold;
    }
    """
    
    def __init__(self, group_id: Optional[int], name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.group_id = group_id
        self.group_name = name
        self._active = False
    
    @property
    def active(self) -> bool:
        return self._active
    
    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        if value:
            self.add_class("active")
        else:
            self.remove_class("active")


class TodoApp(App):
    """Aplicación TODO para terminal con grupos."""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    #main-container {
        width: 100%;
        height: 1fr;
        padding: 0 2;
    }
    
    #tabs-container {
        width: 100%;
        height: 3;
        layout: horizontal;
        padding: 0 1;
    }
    
    #task-list {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    
    #empty-message {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }
    
    #stats {
        dock: bottom;
        width: 100%;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 2;
        text-align: left;
    }
    
    #completed-separator {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        Binding("a", "add_task", "Añadir"),
        Binding("e", "edit_task", "Editar"),
        Binding("d", "delete_task", "Eliminar"),
        Binding("g", "new_group", "Nuevo Grupo"),
        Binding("G", "group_options", "Opc. Grupo"),
        Binding("/", "search", "Buscar"),
        Binding("left", "prev_group", "← Grupo"),
        Binding("right", "next_group", "Grupo →"),
        Binding("space", "toggle_done", "Completar"),
        Binding("enter", "toggle_done", "Completar", show=False),
        Binding("up", "move_up", "Arriba", show=False),
        Binding("down", "move_down", "Abajo", show=False),
        Binding("k", "move_up", "Arriba", show=False),
        Binding("j", "move_down", "Abajo", show=False),
        Binding("h", "prev_group", "", show=False),
        Binding("l", "next_group", "", show=False),
        Binding("q", "quit", "Salir"),
    ]
    
    TITLE = "📋 TODO App"
    
    def __init__(self) -> None:
        super().__init__()
        self.tasks: list[Task] = []
        self.groups: list[Group] = []
        self.next_task_id = 1
        self.next_group_id = 1
        self.selected_index = 0
        self.current_group_id: Optional[int] = None  # None = "Todas"
        self.data_file = self._get_data_path()
        self.load_data()
    
    def _get_data_path(self) -> Path:
        """Obtiene la ruta del archivo de datos según el sistema operativo."""
        import platform
        
        if platform.system() == "Windows":
            # Windows: C:/Users/usuario/todo/todo_tasks.json
            todo_dir = Path.home() / "todo"
        else:
            # Linux/WSL: /home/usuario/todo/todo_tasks.json
            todo_dir = Path.home() / "todo"
        
        # Crear directorio si no existe
        todo_dir.mkdir(exist_ok=True)
        
        return todo_dir / "todo_tasks.json"
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield Horizontal(id="tabs-container")
            yield Container(id="task-list")
            yield Static("Total: 0 | Completadas: 0 | Pendientes: 0 | Grupo: Sin grupo", id="stats")
        yield Footer()
    
    async def on_mount(self) -> None:
        await self.refresh_tabs()
        await self.refresh_task_list()
        self.update_stats()
    
    async def refresh_tabs(self) -> None:
        """Refresca las pestañas de grupos."""
        tabs_container = self.query_one("#tabs-container", Horizontal)
        await tabs_container.remove_children()
        
        # Pestaña "Sin grupo"
        all_tab = GroupTab(None, "📋 Sin grupo", id="tab-all")
        await tabs_container.mount(all_tab)
        all_tab.active = (self.current_group_id is None)
        
        # Pestañas de grupos
        for group in self.groups:
            # Icono de carpeta abierta si está activo, cerrada si no
            icon = "📂" if self.current_group_id == group.id else "📁"
            tab = GroupTab(group.id, f"{icon} {group.name}", id=f"tab-{group.id}")
            await tabs_container.mount(tab)
            tab.active = (self.current_group_id == group.id)
    
    def _get_current_tasks(self) -> list[Task]:
        """Obtiene las tareas del grupo actual."""
        if self.current_group_id is None:
            # "Todas" muestra solo tareas sin grupo asignado
            return [t for t in self.tasks if t.group_id is None]
        return [t for t in self.tasks if t.group_id == self.current_group_id]
    
    async def refresh_task_list(self) -> None:
        """Refresca la lista de tareas en la UI."""
        task_list = self.query_one("#task-list", Container)
        await task_list.remove_children()
        
        current_tasks = self._get_current_tasks()
        pending = [t for t in current_tasks if not t.done]
        completed = [t for t in current_tasks if t.done]
        
        if not current_tasks:
            if self.current_group_id is not None:
                group = next((g for g in self.groups if g.id == self.current_group_id), None)
                if group:
                    msg = f"No hay tareas en '{group.name}'. Pulsa 'a' para añadir."
                else:
                    msg = "No hay tareas. Pulsa 'a' para añadir una."
            else:
                msg = "No hay tareas. Pulsa 'a' para añadir una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            for task in pending:
                widget = TaskWidget(task, id=f"task-{task.id}")
                await task_list.mount(widget)
            
            if completed:
                separator = Static("── Completadas ──", id="completed-separator")
                await task_list.mount(separator)
                
                for task in completed:
                    widget = TaskWidget(task, id=f"task-{task.id}")
                    await task_list.mount(widget)
        
        self._update_selection_after_refresh(pending, completed)
    
    def _update_selection_after_refresh(self, pending: list, completed: list) -> None:
        """Actualiza la selección visual después de refrescar."""
        all_tasks = pending + completed
        if not all_tasks:
            self.selected_index = 0
            return
        
        self.selected_index = max(0, min(self.selected_index, len(all_tasks) - 1))
        
        for i, task in enumerate(all_tasks):
            try:
                widget = self.query_one(f"#task-{task.id}", TaskWidget)
                widget.selected = (i == self.selected_index)
            except Exception:
                pass
    
    def _get_ordered_tasks(self) -> list:
        """Devuelve las tareas actuales ordenadas."""
        current = self._get_current_tasks()
        pending = [t for t in current if not t.done]
        completed = [t for t in current if t.done]
        return pending + completed
    
    def update_selection(self) -> None:
        """Actualiza la selección visual."""
        ordered = self._get_ordered_tasks()
        if not ordered:
            return
        
        self.selected_index = max(0, min(self.selected_index, len(ordered) - 1))
        
        for i, task in enumerate(ordered):
            try:
                widget = self.query_one(f"#task-{task.id}", TaskWidget)
                widget.selected = (i == self.selected_index)
            except Exception:
                pass
    
    def update_stats(self) -> None:
        """Actualiza las estadísticas."""
        current = self._get_current_tasks()
        total = len(current)
        done = sum(1 for t in current if t.done)
        pending = total - done
        
        if self.current_group_id is not None:
            group = next((g for g in self.groups if g.id == self.current_group_id), None)
            group_name = group.name if group else "Sin grupo"
        else:
            group_name = "Sin grupo"
        
        stats_text = f"Total: {total} | Completadas: {done} | Pendientes: {pending} | Grupo: {group_name}"
        stats = self.query_one("#stats", Static)
        stats.update(stats_text)
    
    def get_selected_task_widget(self) -> Optional[TaskWidget]:
        """Obtiene el widget de la tarea seleccionada."""
        ordered = self._get_ordered_tasks()
        if not ordered or self.selected_index >= len(ordered):
            return None
        task = ordered[self.selected_index]
        try:
            return self.query_one(f"#task-{task.id}", TaskWidget)
        except Exception:
            return None
    
    # Acciones de navegación entre grupos
    async def action_prev_group(self) -> None:
        """Cambia al grupo anterior."""
        group_ids = [None] + [g.id for g in self.groups]
        current_idx = group_ids.index(self.current_group_id)
        new_idx = (current_idx - 1) % len(group_ids)
        self.current_group_id = group_ids[new_idx]
        self.selected_index = 0
        await self.refresh_tabs()
        await self.refresh_task_list()
        self.update_stats()
    
    async def action_next_group(self) -> None:
        """Cambia al grupo siguiente."""
        group_ids = [None] + [g.id for g in self.groups]
        current_idx = group_ids.index(self.current_group_id)
        new_idx = (current_idx + 1) % len(group_ids)
        self.current_group_id = group_ids[new_idx]
        self.selected_index = 0
        await self.refresh_tabs()
        await self.refresh_task_list()
        self.update_stats()
    
    # Acción de búsqueda
    def action_search(self) -> None:
        """Busca tareas por texto."""
        def on_search_input(query: Optional[str]) -> None:
            if not query:
                return
            
            # Buscar en todas las tareas
            query_lower = query.lower()
            results: list[tuple[Task, str]] = []
            
            for task in self.tasks:
                if query_lower in task.text.lower():
                    # Obtener nombre del grupo
                    if task.group_id is None:
                        group_name = "Sin grupo"
                    else:
                        group = next((g for g in self.groups if g.id == task.group_id), None)
                        group_name = group.name if group else "Sin grupo"
                    results.append((task, group_name))
            
            if not results:
                # No se encontró nada
                self.push_screen(ConfirmModal(f"No se encontraron tareas para '{query}'"))
            elif len(results) == 1:
                # Solo un resultado: ir directamente al grupo
                task, _ = results[0]
                self._go_to_task(task)
            else:
                # Múltiples resultados: mostrar pantalla de selección
                self.push_screen(SearchResultsScreen(results, query), self._on_search_result)
        
        self.push_screen(InputModal("🔍 Buscar", placeholder="Buscar tareas..."), on_search_input)
    
    def _on_search_result(self, task: Optional[Task]) -> None:
        """Callback cuando se selecciona un resultado de búsqueda."""
        if task:
            self._go_to_task(task)
    
    def _go_to_task(self, task: Task) -> None:
        """Navega al grupo de una tarea y la selecciona."""
        async def do_navigation() -> None:
            # Cambiar al grupo de la tarea
            self.current_group_id = task.group_id
            self.selected_index = 0
            
            await self.refresh_tabs()
            await self.refresh_task_list()
            self.update_stats()
            
            # Seleccionar la tarea en la lista
            ordered = self._get_ordered_tasks()
            for i, t in enumerate(ordered):
                if t.id == task.id:
                    self.selected_index = i
                    break
            self.update_selection()
        
        self.call_later(do_navigation)

    # Acciones de grupos
    def action_new_group(self) -> None:
        """Crea un nuevo grupo."""
        async def on_result(result: Optional[str]) -> None:
            if result:
                group = Group(id=self.next_group_id, name=result)
                self.next_group_id += 1
                self.groups.append(group)
                self.current_group_id = group.id
                self.selected_index = 0
                await self.refresh_tabs()
                await self.refresh_task_list()
                self.update_stats()
                self.save_data()
        
        self.push_screen(InputModal("Nuevo Grupo", placeholder="Nombre del grupo..."), on_result)
    
    def action_group_options(self) -> None:
        """Muestra opciones del grupo actual."""
        if self.current_group_id is None:
            return
        
        group = next((g for g in self.groups if g.id == self.current_group_id), None)
        if not group:
            return
        
        async def on_option(option: str) -> None:
            if option == "rename":
                await self._rename_group(group)
            elif option == "delete":
                await self._delete_group(group)
        
        self.push_screen(GroupOptionsModal(group.name), on_option)
    
    async def _rename_group(self, group: Group) -> None:
        """Renombra un grupo."""
        def on_result(result: Optional[str]) -> None:
            if result:
                group.name = result
                self.call_later(self._after_rename)
        
        self.push_screen(InputModal("Renombrar Grupo", initial_text=group.name), on_result)
    
    async def _after_rename(self) -> None:
        await self.refresh_tabs()
        self.update_stats()
        self.save_data()
    
    async def _delete_group(self, group: Group) -> None:
        """Elimina un grupo y sus tareas."""
        task_count = len([t for t in self.tasks if t.group_id == group.id])
        
        async def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self.tasks = [t for t in self.tasks if t.group_id != group.id]
                self.groups.remove(group)
                self.current_group_id = None
                self.selected_index = 0
                await self.refresh_tabs()
                await self.refresh_task_list()
                self.update_stats()
                self.save_data()
        
        msg = f"¿Eliminar grupo '{group.name}' y sus {task_count} tareas?"
        self.push_screen(ConfirmModal(msg), on_confirm)
    
    # Acciones de tareas
    def action_add_task(self) -> None:
        """Abre el modal para añadir tarea."""
        async def on_result(result: Optional[str]) -> None:
            if result:
                task = Task(
                    id=self.next_task_id, 
                    text=result,
                    group_id=self.current_group_id
                )
                self.next_task_id += 1
                self.tasks.append(task)
                
                current = self._get_current_tasks()
                pending = [t for t in current if not t.done]
                self.selected_index = len(pending) - 1
                
                await self.refresh_task_list()
                self.update_stats()
                self.save_data()
        
        group_name = ""
        if self.current_group_id is not None:
            group = next((g for g in self.groups if g.id == self.current_group_id), None)
            if group:
                group_name = f" en '{group.name}'"
        
        self.push_screen(InputModal(f"Nueva Tarea{group_name}", placeholder="Escribe la tarea..."), on_result)
    
    def action_edit_task(self) -> None:
        """Abre el modal para editar tarea."""
        widget = self.get_selected_task_widget()
        if not widget:
            return
        
        def on_result(result: Optional[str]) -> None:
            if result and widget:
                widget.update_text(result)
                self.save_data()
        
        self.push_screen(
            InputModal("Editar Tarea", initial_text=widget.task_data.text),
            on_result
        )
    
    def action_delete_task(self) -> None:
        """Elimina la tarea seleccionada."""
        ordered = self._get_ordered_tasks()
        if not ordered:
            return
        
        task = ordered[self.selected_index]
        
        async def on_result(confirmed: bool) -> None:
            if confirmed:
                self.tasks.remove(task)
                if self.selected_index >= len(self._get_ordered_tasks()) and self.selected_index > 0:
                    self.selected_index -= 1
                await self.refresh_task_list()
                self.update_stats()
                self.save_data()
        
        text = task.text[:30] + "..." if len(task.text) > 30 else task.text
        self.push_screen(ConfirmModal(f"¿Eliminar '{text}'?"), on_result)
    
    async def action_toggle_done(self) -> None:
        """Alterna el estado de completado."""
        widget = self.get_selected_task_widget()
        if widget:
            widget.toggle_done()
            self.update_stats()
            self.save_data()
            await self.refresh_task_list()
    
    def action_move_up(self) -> None:
        """Mueve la selección arriba."""
        ordered = self._get_ordered_tasks()
        if ordered and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        """Mueve la selección abajo."""
        ordered = self._get_ordered_tasks()
        if ordered and self.selected_index < len(ordered) - 1:
            self.selected_index += 1
            self.update_selection()
    
    # Persistencia
    def save_data(self) -> None:
        """Guarda los datos en disco."""
        data = {
            "next_task_id": self.next_task_id,
            "next_group_id": self.next_group_id,
            "groups": [
                {"id": g.id, "name": g.name}
                for g in self.groups
            ],
            "tasks": [
                {
                    "id": t.id, 
                    "text": t.text, 
                    "done": t.done, 
                    "created_at": t.created_at,
                    "group_id": t.group_id
                }
                for t in self.tasks
            ]
        }
        try:
            self.data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            pass
    
    def load_data(self) -> None:
        """Carga los datos desde disco."""
        try:
            if self.data_file.exists():
                data = json.loads(self.data_file.read_text())
                self.next_task_id = data.get("next_task_id", 1)
                self.next_group_id = data.get("next_group_id", 1)
                
                self.groups = [
                    Group(id=g["id"], name=g["name"])
                    for g in data.get("groups", [])
                ]
                
                self.tasks = [
                    Task(
                        id=t["id"], 
                        text=t["text"], 
                        done=t.get("done", False),
                        created_at=t.get("created_at", ""),
                        group_id=t.get("group_id")
                    )
                    for t in data.get("tasks", [])
                ]
        except Exception:
            self.tasks = []
            self.groups = []
            self.next_task_id = 1
            self.next_group_id = 1


def main():
    app = TodoApp()
    app.run()


if __name__ == "__main__":
    main()