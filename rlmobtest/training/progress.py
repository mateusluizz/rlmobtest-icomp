"""Training progress bar management with Rich."""

import time

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console()


class TrainingProgress:
    """Gerenciador de progresso do treinamento com Rich."""

    def __init__(self, max_time: int | None = None, max_episodes: int | None = None):
        self.max_time = max_time
        self.max_episodes = max_episodes
        self.start_time = time.time()
        self.mode = "time" if max_time else "episodes"

        if self.mode == "time":
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("/"),
                TextColumn(f"[cyan]{self._format_time(max_time)}[/cyan]"),
                console=console,
            )
            self.task = None
        else:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                console=console,
            )
            self.task = None

    def _format_time(self, seconds):
        """Formata segundos para mm:ss ou hh:mm:ss."""
        if seconds < 3600:
            return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def start(self):
        """Inicia a barra de progresso."""
        self.progress.start()
        if self.mode == "time":
            self.task = self.progress.add_task("Training", total=self.max_time)
        else:
            self.task = self.progress.add_task("Training", total=self.max_episodes)

    def update(self, episode=None):
        """Atualiza o progresso."""
        if self.mode == "time":
            elapsed = time.time() - self.start_time
            self.progress.update(self.task, completed=min(elapsed, self.max_time))
        else:
            self.progress.update(self.task, completed=episode)

    def should_stop(self, episode):
        """Verifica se deve parar o treinamento."""
        if self.mode == "time":
            return (time.time() - self.start_time) >= self.max_time
        else:
            return episode >= self.max_episodes

    def stop(self):
        """Para a barra de progresso."""
        self.progress.stop()

    def get_elapsed(self):
        """Retorna tempo decorrido em segundos."""
        return time.time() - self.start_time
