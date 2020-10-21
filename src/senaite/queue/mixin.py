import time
from plone.memoize import ram
from senaite.queue import api

from bika.lims import api as _api


def _generic_5s_key(fun, *args, **kwargs):
    """Returns an string made of the args and kwargs. Used in cache decorators
    """
    params = list(filter(None, args))
    params += sorted(map(lambda i: "{}={}".format(i[0], i[1]), kwargs.items()))
    return "|".join(params), time.time() // 5


@ram.cache(_generic_5s_key)
def _get_uids(status=None):
    return api.get_queue().get_uids(status=status)


class IsQueuedMixin(object):

    def is_queue_active(self, name_or_action=None):
        return api.is_queue_active(name_or_action)

    def is_queued(self, obj, status=None):
        return _api.get_uid(obj) in _get_uids(status=status)
