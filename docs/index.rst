senaite.queue
=============

This add-on enables asynchronous tasks for `SENAITE LIMS`_, that allows to
better handle concurrent actions and processes when the workload is high. Is
specially indicated for high-demand instances and for when there are custom
processes that take long to complete. Essentially, `senaite.queue`_ reduces the
chance of transaction commits by handling tasks asynchronously, in an
unattended and sequential manner.

Once installed, this add-on enables asynchronous processing of those tasks that
usually have a heavier footprint regarding performance, and with highest chance
of transaction conflicts:

* Assignment of analyses to worksheets
* Assignment of worksheet template to a worksheet
* Creation of a worksheet by using a worksheet template
* Workflow actions (submit, verify, etc.) for analyses assigned to worksheets
* Recursive permissions assignment on client contacts creation

This add-on neither provides support for workflow transitions/actions at Sample
level nor for Sample creation. However, this add-on can be extended easily to
match additional requirements.

This documentation is divided in different parts. We recommend that you get
started with :doc:`installation` and then head over to the :doc:`quickstart`.
Please check out :doc:`handling` and :doc:`doctests` for internals about
`senaite.queue`.

Table of Contents:

.. toctree::
   :maxdepth: 2

   installation
   quickstart
   handling
   extend
   doctests
   release_notes
   changelog
   license


.. Links

.. _SENAITE LIMS: https://www.senaite.com
.. _senaite.queue: https://pypi.org/project/senaite.queue

