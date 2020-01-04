from senaite.queue import api
from senaite.queue.queue import queue_action

from bika.lims.browser.workflow import WorkflowActionGenericAdapter


class WorkflowActionGenericQueueAdapter(WorkflowActionGenericAdapter):
    """Adapter in charge of submission of results from a worksheet,
    adding them into a queue for async submission
    """

    def do_action(self, action, objects):
        # Process the first chunk as usual
        chunks = api.get_chunks(action, objects)
        super(WorkflowActionGenericQueueAdapter, self)\
            .do_action(action, chunks[0])

        # Process the rest in a queue
        queue_action(self.context, self.request, action, chunks[1])

        return objects
