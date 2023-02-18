# Copyright (c) 2022 Kyle Schouviller (https://github.com/kyle0654)

from threading import Event, Thread
from .graph import Graph, GraphExecutionState
from .item_storage import ItemStorageABC
from ..invocations.baseinvocation import InvocationContext
from .invocation_services import InvocationServices
from .invocation_queue import InvocationQueueABC, InvocationQueueItem


class InvokerServices:
    """Services used by the Invoker for execution"""
    
    queue: InvocationQueueABC
    graph_execution_manager: ItemStorageABC[GraphExecutionState]

    def __init__(self,
        queue: InvocationQueueABC,
        graph_execution_manager: ItemStorageABC[GraphExecutionState]):
        self.queue           = queue
        self.graph_execution_manager = graph_execution_manager


class Invoker:
    """The invoker, used to execute invocations"""

    services: InvocationServices
    invoker_services: InvokerServices

    __invoker_thread: Thread
    __stop_event: Event

    def __init__(self,
        services: InvocationServices,      # Services used by nodes to perform invocations
        invoker_services: InvokerServices # Services used by the invoker for orchestration
    ):
        self.services = services
        self.invoker_services = invoker_services
        self.__stop_event = Event()
        self.__invoker_thread = Thread(
            name = "invoker",
            target = self.__process,
            kwargs = dict(stop_event = self.__stop_event)
        )
        self.__invoker_thread.daemon = True # TODO: probably better to just not use threads?
        self.__invoker_thread.start()


    def __ensure_alive(self):
        if self.__stop_event.is_set():
            raise Exception("Invoker has been stopped. Must create a new invoker.")


    def __process(self, stop_event: Event):
        try:
            while not stop_event.is_set():
                queue_item: InvocationQueueItem = self.invoker_services.queue.get()
                if not queue_item: # Probably stopping
                    continue

                graph_execution_state = self.invoker_services.graph_execution_manager.get(queue_item.graph_execution_state_id)
                invocation = graph_execution_state.execution_graph.get_node(queue_item.invocation_id)

                # Send starting event
                self.services.events.emit_invocation_started(
                    graph_execution_state_id = graph_execution_state.id,
                    invocation_id = invocation.id
                )

                # Invoke
                outputs = invocation.invoke(InvocationContext(
                    services = self.services,
                    graph_execution_state_id = graph_execution_state.id
                ))

                # Save outputs and history
                graph_execution_state.complete(invocation.id, outputs)

                # Save the state changes
                self.invoker_services.graph_execution_manager.set(graph_execution_state)

                # Send complete event
                self.services.events.emit_invocation_complete(
                    graph_execution_state_id = graph_execution_state.id,
                    invocation_id = invocation.id,
                    result = outputs.dict()
                )

                # Queue any further commands if invoking all
                is_complete = graph_execution_state.is_complete()
                if queue_item.invoke_all and not is_complete:
                    self.invoke(graph_execution_state, invoke_all = True)
                elif is_complete:
                    self.services.events.emit_graph_execution_complete(graph_execution_state.id)

        except KeyboardInterrupt:
            ... # Log something?


    def invoke(self, graph_execution_state: GraphExecutionState, invoke_all: bool = False) -> str|None:
        """Determines the next node to invoke and returns the id of the invoked node, or None if there are no nodes to execute"""
        self.__ensure_alive()

        # Get the next invocation
        invocation = graph_execution_state.next()
        if not invocation:
            return None

        # Save the execution state
        self.invoker_services.graph_execution_manager.set(graph_execution_state)

        # Queue the invocation
        print(f'queueing item {invocation.id}')
        self.invoker_services.queue.put(InvocationQueueItem(
            #session_id    = session.id,
            graph_execution_state_id = graph_execution_state.id,
            invocation_id = invocation.id,
            invoke_all    = invoke_all
        ))

        return invocation.id


    def create_execution_state(self, graph: Graph|None = None) -> GraphExecutionState:
        self.__ensure_alive()
        new_state = GraphExecutionState(graph = Graph() if graph is None else graph)
        self.invoker_services.graph_execution_manager.set(new_state)
        return new_state


    def __stop_service(self, service) -> None:
        # Call stop() method on any services that have it
        stop_op = getattr(service, 'stop', None)
        if callable(stop_op):
            stop_op()


    def stop(self) -> None:
        """Stops the invoker. A new invoker will have to be created to execute further."""
        # First stop all services
        for service in vars(self.services):
            self.__stop_service(service)

        for service in vars(self.invoker_services):
            self.__stop_service(service)

        self.__stop_event.set()
        self.invoker_services.queue.put(None)
