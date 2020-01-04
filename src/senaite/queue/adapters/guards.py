from senaite.queue import api
from senaite.queue.interfaces import IQueued
from zope.interface import implements

from bika.lims.interfaces import IGuardAdapter


class SampleGuardAdapter(object):
    implements(IGuardAdapter)

    def __init__(self, context):
        self.context = context

    def guard(self, action):
        """Returns False if the sample contains one queued analysis
        """
        for brain in self.context.getAnalyses():
            analysis = api.get_object(brain)
            if IQueued.providedBy(analysis):
                return False
        return True
