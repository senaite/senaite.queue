import transaction
from DateTime import DateTime
from senaite.queue import api
from senaite.queue.storage import QueueStorageTool
from senaite.queue.views.dispatcher import QueueDispatcherView

from bika.lims.browser.workflow import WorkflowActionHandler
from bika.lims.utils.analysisrequest import create_analysisrequest
from bika.lims.workflow import doActionFor as do_action_for


def handle_action(context, items_or_uids, action):
    """Simulates the handling of an action when multiple items from a list are
    selected and the action button is pressed
    """
    if not isinstance(items_or_uids, (list, tuple)):
        items_or_uids = [items_or_uids]
    items_or_uids = map(api.get_uid, items_or_uids)
    request = api.get_request()
    request.set("workflow_action", action)
    request.set("uids", items_or_uids)
    WorkflowActionHandler(context, request)()


def create_sample(services, client, contact, sample_type, receive=True):
    """Creates a new sample with the specified services
    """
    request = api.get_request()
    values = {
        'Client': client.UID(),
        'Contact': contact.UID(),
        'DateSampled': DateTime().strftime("%Y-%m-%d"),
        'SampleType': sample_type.UID()
    }
    service_uids = map(api.get_uid, services)
    sample = create_analysisrequest(client, request, values, service_uids)
    if receive:
        do_action_for(sample, "receive")
    return sample


def get_queue_tool():
    """Returns the queue storage tool
    """
    return QueueStorageTool()


def dispatch(request=None):
    """Triggers the Queue Dispatcher
    """
    # Do a transaction commit first. In a test environment, all happens within
    # the same request life-cycle, while in a real environment, the dispatch is
    # always called by a dedicated worker, through an independent thread.
    transaction.commit()
    portal = api.get_portal()
    if not request:
        request = api.get_request()
    return QueueDispatcherView(portal, request)()


def filter_by_state(brains_or_objects, state):
    """Filters the objects passed in by state
    """
    objs = map(api.get_object, brains_or_objects)
    return filter(lambda obj: api.get_review_status(obj) == state, objs)
