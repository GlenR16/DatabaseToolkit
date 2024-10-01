from .database import TASK_TYPES
from background_task import background
from .models import Task

@background(schedule=0)
def task_runner(task_pk: int, run_type: str):
    task = Task.objects.get(pk=task_pk)
    TASK_TYPES[task.type].run(task, run_type)

