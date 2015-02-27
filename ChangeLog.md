Change Log

**Version 1.0.0**

- First release on PyPI. This is the release previously known as 3.0.4 on GitHub.

**Version 1.0.1**

- Queues created through `queue_bind()` were declared with `auto_delete=True`, which made the queue disappear as soon as no more consumers were reading from it. This made the consumer lose all messages waiting in the queue. Fixed by removing the `auto_delete=True` parameter.

**Version 1.0.2**

- Now EQKs may contain queue flags to toggle AMQP parameters such as `auto_delete` on specific queues

**Version 1.1.0**

- Added filters to alter/manage incoming messages before processing them

**Version 1.2.0**

- Added `generic_application.py` with the `GenericApplication` class

**Version 1.2.1**

- Fixed wrong indentation in `generic_application.py`
