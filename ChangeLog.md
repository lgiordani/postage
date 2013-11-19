Change Log
==========

**Version 3.0.1**

- (C) Environment variable `POSTAGE_DEBUG_MODE` can be set to `true` to get a very verbose debug output about AMQP structures and messages
- (C) Some code replication removed: now queue_bind() is the only point where queues are bound to exchanges

**Version 3.0.2**

- (C) `_rpc_send()` was incorrectly using `self.eks[0]` instead of `eks[0]`. As a result RPC signals sent with a custom `_key` were not correctly delivered.

**Version 3.0.3**

- (C) `MessageHandlerType` class double declaration has been removed

**Version 3.0.4**

- (C) Removed double addition of declared queues in `GenericConsumer.add_eqk()`
