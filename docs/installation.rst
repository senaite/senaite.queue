Installation
============

Is strongly recommended to have a SENAITE instance setup in ZEO mode, because
this add-on makes use of a reserved zeo client to dispatch and consume the
queued tasks. In standalone installation, only one CPU / CPU core can be used
for processing requests, with a limited number of threads (usually 2). With a
ZEO mode setup, the database can be used by multiple zeo clients at the same
time, each one using it's own CPU. See `Scalability and ZEO`_ for further
information.

Create a new reserved user in SENAITE instance (under */senaite/acl_users*). The
recommended username is *queue_daemon*.

.. note:: Be sure you create the user in SENAITE's site. Queue won't work with
          acl users created in Zope's root (e.g. *admin*).

This user will be in charge of dispatching queued tasks to a consumer in a
sequential manner. The consumer will eventually process the task, but acting as
the user who initially triggered the process. However, the reserved user
responsible of dispatching must have enough privileges. Assign this user to
the group "Site Administrator" and/or "Manager".

First, add this add-on in the `eggs` section of your buildout configuration file:

.. code-block:: ini

    [buildout]

    ...

    [instance]
    ...
    eggs =
        ...
        senaite.queue


Then, add a new client in your buildout configuration:

.. code-block:: ini

  # Reserved user for dispatching queued tasks
  # See https://pypi.org/project/senaite.queue
  queue-user-name=queue_daemon
  queue-user-password=queue_daemon_password

  parts =
      ....
      client_queue


and configure a reserved client:

.. code-block:: ini

  [client_queue]
  # Client reserved as a worker for async tasks
  <= client_base
  recipe = plone.recipe.zope2instance
  http-address = 127.0.0.1:8089
  zope-conf-additional =
      <clock-server>
          method /senaite/queue_dispatcher
          period 5
          user ${buildout:queue-user-name}
          password ${buildout:queue-user-password}
          host localhost:8089
      </clock-server>


.. note:: This client will listen to port 8089 and is meant to be a reserved
          client, so it should not be accessible to regular users. Thus, if you
          use a load-balancer (e.g HAProxy), is strongly recommended to not add
          this client in the backend pool.

Run `bin/buildout` afterwards.

With this configuration, buildout will download and install the latest published
release of `senaite.queue from Pypi`_.

Once buildout finishes, start the instance, login with a user with "Site
Administrator" privileges and activate the add-on:

http://localhost:8080/senaite/prefs_install_products_form

.. note:: It assumes you have a SENAITE zeo client listening to port 8080

.. Links

.. _senaite.queue from Pypi: https://pypi.org/project/senaite.queue
.. _Scalability and ZEO: https://zope.readthedocs.io/en/latest/zopebook/ZEO.html

