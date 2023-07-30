import os
import socket

import numpy as np
import unittest
from pympipool.shared.communication import SocketInterface
from pympipool.shared.taskexecutor import cloudpickle_register
from pympipool.shared.connections import MpiExecInterface


def calc(i):
    return np.array(i ** 2)


class TestInterface(unittest.TestCase):
    def test_interface(self):
        cloudpickle_register(ind=1)
        task_dict = {"fn": calc, 'args': (), "kwargs": {"i": 2}}
        interface = SocketInterface(
            interface=MpiExecInterface(
                cwd=os.path.abspath("."),
                cores=1,
                gpus_per_core=0,
                oversubscribe=False
            )
        )
        interface.bootup(command_lst=[
            "python",
            os.path.abspath(os.path.join(__file__, "..", "..", "pympipool", "backend", "mpiexec.py"))
        ])
        self.assertEqual(interface.send_and_receive_dict(input_dict=task_dict), np.array(4))
        interface.shutdown(wait=True)