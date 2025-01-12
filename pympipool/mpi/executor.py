from pympipool.shared.executorbase import (
    cloudpickle_register,
    execute_parallel_tasks,
    ExecutorBase,
    executor_broker,
)
from pympipool.shared.interface import MpiExecInterface, SlurmSubprocessInterface
from pympipool.shared.thread import RaisingThread


class PyMPIExecutor(ExecutorBase):
    """
    Args:
        max_workers (int): defines the number workers which can execute functions in parallel
        cores_per_worker (int): number of MPI cores to be used for each function call
        threads_per_core (int): number of OpenMP threads to be used for each function call
        gpus_per_worker (int): number of GPUs per worker - defaults to 0
        oversubscribe (bool): adds the `--oversubscribe` command line flag (OpenMPI only) - default False
        init_function (None): optional function to preset arguments for functions which are submitted later
        cwd (str/None): current working directory where the parallel python task is executed
        sleep_interval (float): synchronization interval - default 0.1
        enable_slurm_backend (bool): enable the SLURM queueing system as backend - defaults to False
    """

    def __init__(
        self,
        max_workers,
        cores_per_worker=1,
        threads_per_core=1,
        gpus_per_worker=0,
        oversubscribe=False,
        init_function=None,
        cwd=None,
        sleep_interval=0.1,
        enable_slurm_backend=False,
    ):
        super().__init__()
        if not enable_slurm_backend:
            if threads_per_core != 1:
                raise ValueError(
                    "The MPI backend only supports threads_per_core=1, "
                    + "to manage threads use the SLURM queuing system enable_slurm_backend=True ."
                )
            elif gpus_per_worker != 0:
                raise ValueError(
                    "The MPI backend only supports gpus_per_core=0, "
                    + "to manage GPUs use the SLURM queuing system enable_slurm_backend=True ."
                )
        self._process = RaisingThread(
            target=executor_broker,
            kwargs={
                # Broker Arguments
                "future_queue": self._future_queue,
                "max_workers": max_workers,
                "sleep_interval": sleep_interval,
                "executor_class": PyMPISingleTaskExecutor,
                # Executor Arguments
                "cores": cores_per_worker,
                "threads_per_core": threads_per_core,
                "gpus_per_task": int(gpus_per_worker / cores_per_worker),
                "oversubscribe": oversubscribe,
                "init_function": init_function,
                "cwd": cwd,
                "enable_slurm_backend": enable_slurm_backend,
            },
        )
        self._process.start()


class PyMPISingleTaskExecutor(ExecutorBase):
    """
    The pympipool.Executor behaves like the concurrent.futures.Executor but it uses mpi4py to execute parallel tasks.
    In contrast to the mpi4py.futures.MPIPoolExecutor the pympipool.Executor can be executed in a serial python process
    and does not require the python script to be executed with MPI. Still internally the pympipool.Executor uses the
    mpi4py.futures.MPIPoolExecutor, consequently it is primarily an abstraction of its functionality to improve the
    usability in particular when used in combination with Jupyter notebooks.

    Args:
        cores (int): defines the number of MPI ranks to use for each function call
        threads_per_core (int): number of OpenMP threads to be used for each function call
        gpus_per_task (int): number of GPUs per MPI rank - defaults to 0
        oversubscribe (bool): adds the `--oversubscribe` command line flag (OpenMPI only) - default False
        init_function (None): optional function to preset arguments for functions which are submitted later
        cwd (str/None): current working directory where the parallel python task is executed
        enable_slurm_backend (bool): enable the SLURM queueing system as backend - defaults to False

    Examples:
        ```
        >>> import numpy as np
        >>> from pympipool.mpi.executor import PyMPISingleTaskExecutor
        >>>
        >>> def calc(i, j, k):
        >>>     from mpi4py import MPI
        >>>     size = MPI.COMM_WORLD.Get_size()
        >>>     rank = MPI.COMM_WORLD.Get_rank()
        >>>     return np.array([i, j, k]), size, rank
        >>>
        >>> def init_k():
        >>>     return {"k": 3}
        >>>
        >>> with PyMPISingleTaskExecutor(cores=2, init_function=init_k) as p:
        >>>     fs = p.submit(calc, 2, j=4)
        >>>     print(fs.result())
        [(array([2, 4, 3]), 2, 0), (array([2, 4, 3]), 2, 1)]
        ```
    """

    def __init__(
        self,
        cores=1,
        threads_per_core=1,
        gpus_per_task=0,
        oversubscribe=False,
        init_function=None,
        cwd=None,
        enable_slurm_backend=False,
    ):
        super().__init__()
        self._process = RaisingThread(
            target=execute_parallel_tasks,
            kwargs={
                # Executor Arguments
                "future_queue": self._future_queue,
                "cores": cores,
                "interface_class": get_interface,
                # Interface Arguments
                "threads_per_core": threads_per_core,
                "gpus_per_core": gpus_per_task,
                "cwd": cwd,
                "oversubscribe": oversubscribe,
                "enable_slurm_backend": enable_slurm_backend,
            },
        )
        self._process.start()
        self._set_init_function(init_function=init_function)
        cloudpickle_register(ind=3)


def get_interface(
    cores=1,
    threads_per_core=1,
    gpus_per_core=0,
    cwd=None,
    oversubscribe=False,
    enable_slurm_backend=False,
):
    if not enable_slurm_backend:
        return MpiExecInterface(
            cwd=cwd,
            cores=cores,
            threads_per_core=threads_per_core,
            gpus_per_core=gpus_per_core,
            oversubscribe=oversubscribe,
        )
    else:
        return SlurmSubprocessInterface(
            cwd=cwd,
            cores=cores,
            threads_per_core=threads_per_core,
            gpus_per_core=gpus_per_core,
            oversubscribe=oversubscribe,
        )
