from __future__ import annotations
import typing as tp
import asyncio
from os import path
from sys import argv, stderr
from traceback import format_exc
from functools import partial

from .root import root, Node

if tp.TYPE_CHECKING:
    from mpi4py.MPI import Intracomm


class MPI(Node):
    """Node for current MPI workspace."""
    # Index of current MPI process
    rank: int

    # Total number of MPI processes
    size: int

    # MPI Comm World
    comm: Intracomm

    # Default file name of current process
    @property
    def pid(self):
        return f'p{"0" * (len(str(self.size - 1)) - len(str(self.rank)))}{self.rank}'
    
    def mpiload(self, src: str = '.'):
        """Read from a MPI directory."""
        if self.has(fname := path.join(src, self.pid + '.npy')):
            return self.load(fname)
        
        return self.load(path.join(src, self.pid + '.pickle'))
    
    def mpidump(self, obj, dst: str = '.'):
        """Save with MPI file name."""
        from numpy import ndarray

        ext = '.npy' if isinstance(obj, ndarray) else '.pickle'
        self.dump(obj, path.join(dst, self.pid + ext), mkdir=False)


def _call(size: int, idx: int):
    mpidir = path.dirname(argv[1]) or '.'
    root.init(mpidir=mpidir)

    if size == 0:
        # use mpi
        from mpi4py.MPI import COMM_WORLD as comm

        root.mpi.comm = comm
        root.mpi.rank = comm.Get_rank()
        root.mpi.size = comm.Get_size()

    else:
        # use multiprocessing
        root.mpi.rank = idx
        root.mpi.size = size
    
    # saved function and arguments from main process
    (func, arg, arg_mpi) = root.load(f'{argv[1]}.pickle')

    # determine function arguments
    args = []

    if arg is not None:
        args.append(arg)

    if arg_mpi is not None:
        args.append(arg_mpi[root.mpi.rank])

    # call target function
    if callable(func):
        if asyncio.iscoroutine(result := func(*args)):
            asyncio.run(result)
    
    else:
        from subprocess import check_call
        check_call(func, shell=True, cwd=mpidir)


if __name__ == '__main__':
    try:
        if len(argv) > 3 and argv[2] == '-mp':
            # use multiprocessing
            np = int(argv[3])

            if np == 1:
                _call(np, 0)
            
            else:
                from multiprocessing import Pool

                with Pool(processes=np) as pool:
                    pool.map(partial(_call, np), range(np))
        
        else:
            # use mpi
            _call(0, 0)
    
    except Exception:
        err = format_exc()
        print(err, file=stderr)
        root.write(err, f'{argv[1]}.error', 'a')
