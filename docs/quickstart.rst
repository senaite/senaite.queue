Quickstart
==========

This section gives an introduction about `senaite.queue`_. It assumes you
have `SENAITE LIMS`_ and `senaite.queue` already installed, with a reserved zeo
client listening at port 8089 and a regular zeo client listening at port 8080.
Please read the :doc:`installation` for further details.

.. _QueueControlPanel:

Queue control panel
-------------------

Visit the control panel view for `senaite.queue` to configure the settings.
This control panel is accessible to users with `Site Administrator` role,
through "Site Setup" view, "Add-on Configuration" section:

http://localhost:8080/senaite/@@queue-controlpanel

In most cases, the settings that come by default will fit well. Modifying some
of them might speed-up the processing of queued tasks, but might also increase
the chance of conflicts. Therefore, is strongly recommended to monitor the
instance while modifying this settings.

Queueing a task
---------------

Login as a SENAITE regular user with "Lab Manager" privileges. Be sure there
are some analyses awaiting for assignment and create a worksheet, either by
manually assigning some analyses or by using a Worksheet Template. As soon as
the worksheet is created, the system displays a viewlet stating that some
analyses have been queued for the current worksheet:

.. image:: static/worksheet_queued_analyses_viewlet.png
  :width: 401
  :alt: Viewlet showing the number of queued analyses in a Worksheet

Keep pressing the "Refresh" button and the message will eventually disappear, as
soon as the reserved client finishes processing the task.

.. note:: If you don't see any change after refreshing the page several times,
          check that you have the queued reserved client running in background
          and the reserved user for the queue is properly configured.

Queue monitoring
----------------

The queue monitoring view is accessible from the top-right "hamburger" menu,
link "Queue Monitor":

http://localhost:8080/senaite/queue_tasks

The failed, running and queued tasks are displayed in this view, along with
their Task Unique Identifiers (TUIDs). From this view, the user can manually
re-queue or remove tasks at a glance:

.. image:: static/queue_monitor.png
  :width: 1084
  :alt: Queue monitor view

Failed tasks shouldn't be the norm, but there is always the chance that a task
cannot complete. In order to provide insights about the reason/s behind a
failure, the monitor listing displays also the error trace raised by the system
when trying to process the task. In this example, system was not able to process
the first task because the user who triggered the task is not from SENAITE's
domain.

The "retries" column indicates the number of attempts before the task being
considered as failed and therefore, discarded for further processing.

Queued task details
-------------------

Given a TUID, the user can see the whole information of a given task in JSON
format. The TUID of each task displayed in the Queue Monitoring view explained
above is a link to the full detail of the task:

.. code-block:: javascript

    {
        "status": "queued",
        "context_uid": "67127b454506455f81d69921beec4e93",
        "context_path": "/senaite/worksheets/WS-018",
        "name": "task_action_submit",
        "retries": 5,
        "uids": [
            "bc0c7489fa974e74b68a680568608277",
            "7e6cc0c0de9449ca953dd8b7dfaffb96",
            "2f8f2a05faa14af19545e9f08b4b282c",
            "b2bd04cb1755493186bea52a50f37326",
            "5531c1adc95e47c38ff11c49ff8ff50b",
            "ef19831a8ef9467db401008c1269b937"
        ],
        "created": 1598626797.74663,
        "error_message": null,
        "request": {
            "__ac": "ol4yjEYYg82gR14ZIbh1vI2zrD3i+LfBp30+G6MyyPw1ZjQ5MTMzOWFpYnN0IQ==",
            "HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0",
            "X_REAL_IP": "",
            "_orig_env": {
                "SERVER_SOFTWARE": "Zope/(2.13.28, python 2.7.16, linux2) ZServer/1.1",
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/senaite/worksheets/WS-018/workflow_action",
                "SERVER_PROTOCOL": "HTTP/1.1",
                ...
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "HTTP_ACCEPT_ENCODING": "gzip, deflate"
            },
            "HTTP_REFERER": "http://localhost:8080/senaite/worksheets/WS-018/manage_results",
            "REMOTE_ADDR": "127.0.0.1",
            "AUTHENTICATED_USER": "analyst1",
            "X_FORWARDED_FOR": "",
            "_ZopeId": "68044235A9oxFuzwE6o"
        },
        "priority": 10,
        "max_seconds": 60,
        "task_uid": "2bb771e4bb7cbcf9625bf761377292d8",
        "action": "submit",
        "min_seconds": 2
    }

The fields displayed might vary depending on the type of task (the "name" field
defines the type of the task). In the example above, the task refers to the
submission (field `action`) of results for 6 analyses from worksheet with id
"WS-018" (field `context_path`). This action has been triggered by the user
with id "analyst1" (field `AUTHENTICATED_USER`). The field `uids`
contains the unique identifiers of the analyses to be submitted, and the
`context_uid` indicates the unique identifier of the object from which the
action/task has been triggered.


.. note:: There are plenty of add-ons for browsers that beautify the generated
          JSON, making it's interpretation more comfortable for humans. These
          are some of the plugins you might consider to install in your browser:
          `JSONView for Firefox`_, `JSON Lite for Firefox`_,
          `JSONView for Google Chrome`_


.. Links

.. _senaite.queue: https://pypi.python.org/pypi/senaite.queue
.. _SENAITE LIMS: https://www.senaite.com
.. _JSONView for Firefox: https://addons.mozilla.org/de/firefox/addon/jsonview
.. _JSON Lite for Firefox: https://addons.mozilla.org/en-US/firefox/addon/json-lite
.. _JSONView for Google Chrome: https://chrome.google.com/webstore/detail/jsonview/chklaanhfefbnpoihckbnefhakgolnmc?hl=en
