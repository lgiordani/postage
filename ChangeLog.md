Change Log
==========

**Version 3.0.1**

- (C) Environment variable `POSTAGE_DEBUG_MODE` can be set to `true` to get a very verbose debug output about AMQP structures and messages
- (C) Some code replication removed: now queue_bind() is the only point where queues are bound to exchanges
