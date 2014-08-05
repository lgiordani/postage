.. :changelog:

History
-------

1.0.0 (2013-12-03)
++++++++++++++++++

* First release on PyPI.

1.0.1 (2014-06-05)
++++++++++++++++++

* Queues created through queue_bind() were declared with auto_delete=True, which made the queue disappear as soon as no more consumers were reading from it. This made the consumer lose all messages waiting in the queue. Fixed by removing the auto_delete=True parameter.


1.0.2 (2014-08-05)
++++++++++++++++++

* Now EQKs may contain queue flags to toggle AMQP parameters such as auto_delete on specific queues