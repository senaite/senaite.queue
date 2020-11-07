Installation
============

Is strongly recommended to have a SENAITE instance setup in ZEO mode, because
this add-on is especially useful when a reserved zeo client is used to act as
a queue server and at least one additional zeo client for tasks consumption.

In standalone installation, only one CPU / CPU core can be used for processing
requests, with a limited number of threads (usually 2). With a ZEO mode setup,
the database can be used by multiple zeo clients at the same time, each one
using it's own CPU. See `Scalability and ZEO`_ for further information.

Create a new reserved user in SENAITE instance (under */senaite/acl_users*). The
recommended username is *queue_consumer*.

This user will be used by the consumer to pop tasks from the queue server in a
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


Then, add a two clients (a consumer and the server) in your buildout
configuration:

.. code-block:: ini

    # Reserved user for dispatching queued tasks
    # See https://pypi.org/project/senaite.queue
    queue-user-name=queue_consumer
    queue-user-password=queue_consumer_password

    parts =
        ....
        queue_consumer
        queue_server


and configure two reserved clients:

.. code-block:: ini

    [queue_consumer]
    # ZEO Client reserved for the consumption of queued tasks
    <= client_base
    recipe = plone.recipe.zope2instance
    http-address = 127.0.0.1:8089
    zope-conf-additional =
        <clock-server>
            method /senaite/queue_consume
            period 5
            user ${buildout:queue-user-name}
            password ${buildout:queue-user-password}
            host localhost:8089
        </clock-server>

    [queue_server]
    # ZEO Client reserved to act as the server of the queue
    <= client_base
    recipe = plone.recipe.zope2instance
    http-address = 127.0.0.1:8090

.. note:: These clients will listen to ports 8089 and 8090. They should not be
          accessible to regular users. Thus, if you use a load-balancer
          (e.g HAProxy), is strongly recommended to not add these clients in
          the backend pool.

In most scenarios, this configuration is enough. However, senaite.queue supports
multi consumers, that can be quite useful for those SENAITE installations that
have a very high overload. To add more consumers, add as many zeo client
sections as you need with the additional `clock-server` zope configuration. Do
not forget to set the value `host` correctly to all them, because this value is
used by the queue server to identify the consumers when tasks are requested.

The maximum number of concurrent consumers supported by the queue server is 4.

Run `bin/buildout` afterwards. With this configuration, buildout will download
and install the latest published release of `senaite.queue from Pypi`_.

.. note:: If the buildout fails with a ``ImportError: cannot import name aead``,
          please update OpenSSL to v1.1.1 or above. OpenSSL v1.0.2 is no longer
          supported by ``cryptography`` starting from v3.2. Please, read the
          `changelog from cryptography`_ for further information. Although not
          recommended, you can alternatively stick to version 3.1.1 by adding
          ``cryptography=3.1.1`` in ``[versions]`` section from your buildout.

Once buildout finishes, start the clients:

.. code-block:: shell

    $ sudo -u plone_daemon bin/client1 start
    $ sudo -u plone_daemon bin/queue_server start
    $ sudo -u plone_daemon bin/queue_client start

.. note:: ``plone_daemon`` is the default user created by the quick-installer
          when installing Plone in ZEO cluster mode. Please check
          `Installation of Plone`_ for further information. You might need to
          change this user name depending on how you installed SENAITE.

Then visit your SENAITE site and login with a user with "Site Administrator"
privileges to activate the add-on:

http://localhost:8080/senaite/prefs_install_products_form

.. note:: It assumes you have a SENAITE zeo client listening to port 8080

Once activated, go to `Site Setup > Queue Settings` and, in field "Queue Server",
type the url of the zeo client that will act as the server of the queue.

http://localhost:8090/senaite

.. note:: Do not forget to specify the site id in the url (usually "senaite")


.. Links

.. _senaite.queue from Pypi: https://pypi.org/project/senaite.queue
.. _Scalability and ZEO: https://zope.readthedocs.io/en/latest/zopebook/ZEO.html
.. _changelog from cryptography: https://cryptography.io/en/latest/changelog.html#v3-2
.. _Installation of Plone: https://docs.plone.org/4/en/manage/installing/installation.html#how-to-install-plone
