'''
'''
from __future__ import annotations
from multiprocessing import Pool, Manager, Value
from multiprocessing.managers import ValueProxy
import importlib
from dataclasses import dataclass
import time
import math
import os
import logging
import logging.config
import traceback
from typing import Tuple, Dict, Any
from types import ModuleType
from queue import Queue

LOGGER_NAME = 'job_logger'
COOLDOWN = 'cooldown'
DEFAULT_COOLDOWN = 1

@dataclass
class Message:
    is_kill_message: bool
    module_path: str
    parameters: list

    @staticmethod
    def get_kill_message() -> Message:
        return Message(True, '', [])

    @staticmethod
    def get_execution_message(module_path: str, parameters: list) -> Message:
        return Message(False, module_path, parameters)


class WorkerPool:
    manager: Manager
    running: int
    job_queue: Queue
    pool: Pool
    result_queues: Dict[str, Queue]
    main_jobs: int

    def __init__(self: WorkerPool, pool_size: int = 0) -> None:
        logging.config.fileConfig('logging.config', defaults={'log_filename': 'pool'})
        self.manager = Manager()
        self.running = self.manager.Value('i', 0)
        self.job_queue = self.manager.Queue()
        self.pool = Pool(pool_size) if pool_size else Pool()
        self.result_queues = {}
        self.main_jobs = 0

    def stop(self: WorkerPool) -> None:
        self.running.value = 0

    def start(self: WorkerPool, modules: Dict[str, Any]): # -> module_path, timings
        self.main_jobs = len(modules)
        self.running.value = 1
        results = []

        for module_path, module_config in modules.items():
            self.result_queues[module_path] = self.manager.Queue()
            results.append(self.pool.apply_async(
                WorkerPool.run_job, 
                (self.running, self.job_queue, self.result_queues[module_path], module_path, module_config)
            ))

        self.read_queue()

        return [result.get() for result in results]

    def read_queue(self: WorkerPool) -> None:
        while self.main_jobs != 0:
            while self.job_queue.empty():
                time.sleep(2)
            message = self.job_queue.get()

            if message.is_kill_message:
                self.main_jobs -= 1
                logging.getLogger(LOGGER_NAME).info('Got kill message')
            else:
                self.pool.apply_async(
                    WorkerPool.run_sub_job,
                    (message.module_path, message.parameters),
                    callback=lambda result: self.result_queues[message.module_path].put(result)
                )
        self.pool.close()
        self.pool.join()

    @staticmethod
    def run_module(module: ModuleType, module_path: str, job_queue: Queue, result_queue: Queue, run_async: bool, async_cores: int, split_async: bool, args: Dict[str, Any]) -> bool:
        try:
            if not hasattr(module, 'run_query'):
                module.execute_job(**args)
                return True
            queried_data = module.run_query(**args)
            if not any(queried_data):
                return False
            extra_args = getattr(module, 'EXECUTE_NEEDS_ARGS', False)
            if not run_async:
                results = [module.execute_job(queried_data, **args) if extra_args else module.execute_job(queried_data)]
            else:
                async_cores = async_cores if async_cores != 0 else os.cpu_count()
                if split_async:
                    queried_data = WorkerPool.split_parameters(queried_data, async_cores)
                for queried_chunk in queried_data:
                    job_queue.put(Message.get_execution_message(module_path, (queried_chunk, args) if extra_args else queried_chunk))
                results = []
                while len(results) != len(queried_data):
                    results.append(result_queue.get())
            module.summarize_results(results)
            return True
        except Exception as ex:
            logging.getLogger(LOGGER_NAME).info(f'There was an error while running the module {module_path}: {traceback.format_exc()}')
            return False

    @staticmethod
    def run_job(running, job_queue, result_queue, module_path, module_config) -> Tuple[str, float]:
        module = importlib.import_module(module_path)
        args = module_config['args']
        timings = []
        iterations = module_config.get('iterations', math.inf)
        run_async = module_config.get('run_async', False)
        async_cores = module_config.get('async_cores', 0)
        split_async = module_config.get('split_async', True)
        cooldown = module_config.get(COOLDOWN, DEFAULT_COOLDOWN)
        no_work_timeout = module_config.get('no_work_timeout', -1)
        iteration = 0
        while running.value and iteration < iterations:
            start_time = time.time()
            worked = WorkerPool.run_module(module, module_path, job_queue, result_queue, run_async, async_cores, split_async, args)
            if worked and len(timings) < 30:
                timings.append(time.time() - start_time)
            iteration += 1
            if worked:
                time.sleep(cooldown)
            elif no_work_timeout == -1:
                break
            else:
                time.sleep(no_work_timeout)
        
        job_queue.put(Message.get_kill_message())
        return module_path, timings

    @staticmethod
    def run_sub_job(module_path, parameters):
        module = importlib.import_module(module_path)
        if parameters:
            result = module.execute_job(parameters[0], **parameters[1]) if getattr(module, 'EXECUTE_NEEDS_ARGS', False) else module.execute_job(parameters)
        else:
            result = module.execute_job()
        return result

    @staticmethod
    def split_parameters(parameters, pool_size):
        chunk_size = max(len(parameters) // pool_size, 1)
        return [parameters[i:i+chunk_size] for i in range(0, len(parameters), chunk_size)]
