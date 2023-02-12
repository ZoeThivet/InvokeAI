# Copyright (c) 2022 Kyle Schouviller (https://github.com/kyle0654)

from argparse import Namespace
import os
import sys
import traceback

import ldm.invoke

from ...globals import Globals

from ..services.image_storage import DiskImageStorage
from ..services.session_manager import DiskSessionManager
from ..services.invocation_queue import MemoryInvocationQueue
from ..services.invocation_services import InvocationServices
from ..services.invoker import Invoker, InvokerServices
from ..services.generate_initializer import get_generate
from .events import FastAPIEventService


# TODO: is there a better way to achieve this?
def check_internet()->bool:
    '''
    Return true if the internet is reachable.
    It does this by pinging huggingface.co.
    '''
    import urllib.request
    host = 'http://huggingface.co'
    try:
        urllib.request.urlopen(host,timeout=1)
        return True
    except:
        return False


class ApiDependencies:
    """Contains and initializes all dependencies for the API"""
    invoker: Invoker = None

    @staticmethod
    def initialize(
        args,
        config,
        event_handler_id: int
    ):
        Globals.try_patchmatch = args.patchmatch
        Globals.always_use_cpu = args.always_use_cpu
        Globals.internet_available = args.internet_available and check_internet()
        Globals.disable_xformers = not args.xformers
        Globals.ckpt_convert = args.ckpt_convert

        # TODO: Use a logger
        print(f'>> Internet connectivity is {Globals.internet_available}')

        generate = get_generate(args, config)

        events = FastAPIEventService(event_handler_id)

        output_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../outputs'))

        images = DiskImageStorage(output_folder)

        services = InvocationServices(
            generate = generate,
            events   = events,
            images   = images
        )

        invoker_services = InvokerServices(
            queue = MemoryInvocationQueue(),
            session_manager = DiskSessionManager(output_folder)
        )

        ApiDependencies.invoker = Invoker(services, invoker_services)
    
    @staticmethod
    def shutdown():
        if ApiDependencies.invoker:
            ApiDependencies.invoker.stop()
