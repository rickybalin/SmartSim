import datetime
import time
import numpy as np
from threading import Thread

from ..error import SSConfigError
from ..utils import get_logger, get_env

logger = get_logger(__name__)

try:
    level = get_env("SMARTSIM_LOG_LEVEL")
    verbose_tm = True if level == "developer" else False
except SSConfigError:
    verbose_tm = False


class TaskManager:
    """The Task Manager watches the subprocesses launched through
    the asyncronous shell interface. Each task is a wrapper
    around the popen that links it to the id of the Job instance
    it is connected to.

    The Task manager can be optionally added to any launcher interface
    to have greater control over the entities that are launched.

    The task manager connects to the job manager through the launcher
    so as to not break encapsulation between the controller and launcher.

    Each time a status is requested, a launcher can check the task
    manager to ensure that the task is still alive and well.
    """

    # time to wait between status checks
    interval = 3

    def __init__(self):
        """Initialize a task manager thread."""
        self.name = "TaskManager" + "-" + str(np.base_repr(time.time_ns(), 36))
        self.actively_monitoring = False
        self.statuses = dict()
        self.tasks = []

    def start(self):
        """Start the task manager thread"""
        monitor = Thread(name=self.name, daemon=True, target=self.run)
        monitor.start()

    def run(self):
        """Start the loop that continually checks tasks for status.

        One piece to note is that if a command server is used, the
        output and error of the task will not be propagated through
        the command schema. This is because piped Popens cannot be
        serialized.
        """
        global verbose_tm
        if verbose_tm:
            logger.debug("Starting Task Manager thread: " + self.name)

        self.actively_monitoring = True
        while self.actively_monitoring:
            time.sleep(self.interval)
            if verbose_tm:
                logger.debug(f"{self.name} - Active Tasks: {len(self.tasks)}")
                logger.debug(
                    f"{self.name} - Task Returncodes: {[task.returncode for task in self.tasks]}"
                )

            for task in self.tasks:
                returncode = task.check_status()
                if returncode and returncode != 0:
                    # TODO set this up for the command server so users know
                    output, error = "", ""
                    if task.has_piped_io:
                        output, error = task.get_io()
                    self.statuses[task.step_id] = (returncode, output, error)
                    self.remove_task(task)
                elif returncode == 0:
                    self.remove_task(task)

            if len(self.tasks) == 0:
                self.actively_monitoring = False
                if verbose_tm:
                    logger.debug(f"{self.name} - Sleeping, no tasks to monitor")

    def add_task(self, popen_process, step_id):
        """Create and add a task to the TaskManager

        :param popen_process: Popen object
        :type popen_process: subprocess.Popen
        :param step_id: id gleaned from the launcher
        :type step_id: str
        """
        task = Task(popen_process, step_id)
        if verbose_tm:
            logger.debug(f"{self.name}: Adding Task {task.pid}")
        self.tasks.append(task)

    def remove_task(self, task):
        """Remove a task from the TaskManager

        :param task: The instance of the Task
        :type task: Task
        """
        if verbose_tm:
            logger.debug(f"{self.name}: Removing Task {task.pid}")
        self.tasks.remove(task)
        task.kill()

    def get_task_status(self, step_id):
        """Get the task status by step_id

        :param step_id: step_id of the job
        :type step_id: str
        """
        return self.statuses[step_id]

    def __getitem__(self, step_id):
        for task in self.tasks:
            if task.step_id == step_id:
                return task
        raise KeyError


class Task:
    """A Task is a wrapper around a Popen object that includes a reference
    to the Job id created by the launcher. For the local launcher this
    will just be the pid of the Popen object
    """

    def __init__(self, popen_process, step_id):
        """Initialize a task

        :param popen_process: Popen object
        :type popen_process: subprocess.Popen
        :param step_id: Id from the launcher
        :type step_id: str
        """
        self.process = popen_process
        self.step_id = step_id  # dependant on the launcher type

    def has_piped_io(self):
        """When jobs are spawned using the command server they
           will not have any IO as you cannot serialize a Popen
           object with open PIPEs

        :return: boolean for if Popen has PIPEd IO
        :rtype: bool
        """
        if self.process.stdout or self.process.stderr:
            return True
        return False

    def check_status(self):
        """Ping the job and return the returncode if finished

        :return: returncode if finished otherwise None
        :rtype: int
        """
        return self.process.poll()

    def get_io(self):
        """Get the IO from the subprocess

        :return: output and error from the Popen
        :rtype: str, str
        """
        output, error = self.process.communicate()
        return output.decode("utf-8"), error.decode("utf-8")

    def kill(self):
        """Kill the subprocess"""
        self.process.kill()

    @property
    def pid(self):
        return self.process.pid

    @property
    def returncode(self):
        return self.process.returncode


class Status:
    """Status objects are created to hold the status of a task information
    between the Task and Job managers. In order to communicate the job
    information back to the JobManager, Status objects are created and
    given to the Launcher that spawned the jobs. When the JobManager asks
    for Job statuses, if an error has occured in the job, a Status object
    will be waiting in the launcher.
    """

    def __init__(self, status="", returncode=None, output=None, error=None):
        self.status = status
        self.returncode = returncode
        self.output = output
        self.error = error