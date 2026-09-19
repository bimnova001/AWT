from core.task import (
    Task,
    TaskStatus
)


class TaskGraph:

    def __init__(self):

        self.tasks = {}

    def add(
        self,
        task: Task
    ):

        self.tasks[
            task.task_id
        ] = task

        if task.parent_task_id:

            parent = self.get(
                task.parent_task_id
            )

            if parent:

                if task.task_id not in parent.children:

                    parent.children.append(
                        task.task_id
                    )

    def get(
        self,
        task_id: str
    ):

        return self.tasks.get(
            task_id
        )

    def create_subtask(
        self,
        parent: Task,
        description: str,
        capabilities: list[str],
        created_by: str,
        target_agent: str | None = None
    ):

        task = Task(

            parent_task_id=parent.task_id,

            description=description,

            required_capabilities=capabilities,

            created_by=created_by,

            assigned_agent=target_agent,

            status=TaskStatus.PROPOSED,

        )

        self.add(task)

        return task

    def children(
        self,
        task: Task
    ):

        return [

            self.tasks[task_id]

            for task_id in task.children

            if task_id in self.tasks

        ]

    def all_children_completed(
        self,
        task: Task
    ):

        children = self.children(
            task
        )

        if not children:

            return True

        return all(
            child.status
            == TaskStatus.COMPLETED
            for child in children
        )

    def all_children_finished(
        self,
        task: Task
    ):

        children = self.children(
            task
        )

        if not children:

            return True

        return all(

            child.status in {

                TaskStatus.COMPLETED,

                TaskStatus.FAILED,

                TaskStatus.CANCELLED,

            }

            for child in children

        )

    def get_root(
        self
    ):

        roots = [

            task

            for task in self.tasks.values()

            if task.parent_task_id is None

        ]

        return roots[0] if roots else None

    def count(self):

        return len(
            self.tasks
        )