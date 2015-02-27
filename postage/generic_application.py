import os
import messaging

class GenericApplicationExchange(messaging.Exchange):

    """The GenericApplication exchange, used to send normal messages."""

    name = "generic-application-exchange"
    exchange_type = "direct"
    passive = False
    durable = True
    auto_delete = False


class LoggingProducerStub(object):

    """This is just a stub logger that may be replaced by an actual producer."""

    def __init__(self, fingerprint={}, hup=None, vhost=None):
        pass

    def stub(self, *args, **kwds):
        pass

    def __getattr__(self, attr):
        return self.stub


class GenericApplication(messaging.MessageProcessor):

    # This is the standard exchange the application connects to
    exchange_class = GenericApplicationExchange

    # This is the producer the application will use to log messages
    # The stub does nothing, you have to replace it with an actual
    # producer
    logging_producer = LoggingProducerStub

    def __init__(self, fingerprint, vhost, groups=[]):
        super(GenericApplicationConsumerMicroThread, self).__init__(
            fingerprint, [], None, vhost)

        self.logger = self.logging_producer(self.fingerprint)

        # The RabbitMQ virtual host this application is running on
        self.vhost = vhost
        if self.vhost is None:
            self.vhost = messaging.global_vhost

        # The name of this application
        name = self.fingerprint['name']

        # The OS pid of this application
        pid = self.fingerprint['pid']

        # The host running this application
        host = self.fingerprint['host']

        # The system-wide queue (System queue IDentifier)
        # All application with the same 'name' share this queue
        self.sid = {'name': name, 'flags': {'auto_delete': True}}

        # The host-wide queue (Host queue IDentifier)
        # All application with the same 'name' on the same 'host'
        # share this queue
        self.hid = {'name': "%s@%s" %
                    (name, host), 'flags': {'auto_delete': True}}

        # The unique queue (Unique queue IDentifier)
        # Only this application owns this queue since the (pid, host)
        # tuple is unique
        self.uid = {'name': "%s@%s" %
                    (pid, host), 'flags': {'auto_delete': True}}

        # Applications may belong to one or more groups
        self.groups = groups

        # Name and host could be two automatic groups. They are however treated
        # in a special way to
        # 1. avoid creating group names that can clash
        # with user-defined ones and
        # 2. give a standard syntax that isolates two important values that are
        # always present.

        # The standard queue/key bindings for an application.
        standard_qk_bindings = [
            # Round-robin by name
            # Each application with the same name subscribes this key with its
            # system-wide queue (shared among applications).
            # This key thus implements the Round Robin mechanism. This is the
            # standard AMQP load balancer.
            (self.sid, "{name}/rr".format(name=name)),

            # Fanout by name
            # Each application with the same name subscribes this key with its
            # unique queue.
            # This key implements a Fanout service.
            (self.uid, "{name}".format(name=name)),

            # Fanout by host
            # Each application running on the same host subscribes this key
            # with its unique queue.
            # This key implements a Fanout service.
            (self.uid, "@{host}".format(host=host)),

            # Round-robin by name and host
            # Each application with the same name running on the same host
            # subscribes this key with its system-wide queue
            # (shared among applications).
            # This key thus implements the Round Robin mechanism. This is the
            # standard AMQP load balancer.
            (self.hid, "{name}@{host}/rr".format(name=name, host=host)),

            # Fanout by name and host
            # Each application with the same name running on the same host
            # subscribes this key with its unique queue.
            # This key implements a Fanout service.
            (self.uid, "{name}@{host}".format(name=name, host=host)),

            # Unique address
            # Only this application subscribes to this key with its unique
            # queue
            (self.uid, "{pid}@{host}".format(pid=pid, host=host))
        ]

        self.add_eqk([(self.exchange_class, standard_qk_bindings)])

        for group in self.groups:
            # Fanout by app#group
            # Each application with the same name name and belonging to the same
            # group subscribes this key with its unique queue
            self.logger.log(
                "Joining group {name}#{group}".format(name=name, group=group))

            self.consumer.queue_bind(
                self.exchange_class,
                self.uid,
                "{name}#{group}".format(name=name, group=group)
            )

            # Round-robin by app#group
            # Each application with this name and belonging to this group
            # subscribes this key with its personal queue
            self.logger.log(
                "Joining group {name}#{group}/rr".format(name=name,
                                                         group=group))

            self.consumer.queue_bind(
                self.exchange_class,
                "{name}#{group}".format(name=name, group=group),
                "{name}#{group}/rr".format(name=name, group=group)
            )

    @messaging.RpcHandler('command', 'ping')
    def msg_ping(self, content, reply_func):
        reply_func(messaging.MessageResult(self.fingerprint))

    @messaging.MessageHandler('command', 'join_group')
    def msg_join_group(self, content):
        group = content['parameters']['group_name']
        name = self.fingerprint['name']
        if group not in self.groups:
            self.groups.append(group)

            # Fanout by app#group
            # Each application with the same name and belonging to the same
            # group subscribes this key with its unique queue
            self.logger.log(
                "Joining group {name}#{group}".format(name=name, group=group))

            self.consumer.queue_bind(
                self.exchange_class,
                self.uid,
                "{name}#{group}".format(name=name, group=group)
            )

            # !!!!!!!!!!!!!
            # Round-robin on groups cannot be done: all components connect to
            # the same queue. When you unbind it, you unbind the same queue.
            # The first unbinds the queue, the second crashes.
            # Moreover if the queue is new (as happens here) we shall
            # issue basic_consume() (for each queue)
            # and then start_consuming() (once): this means restarting.

    @messaging.MessageHandler('command', 'leave_group')
    def msg_leave_group(self, content):
        group=content['parameters']['group_name']
        name=self.fingerprint['name']
        if group in self.groups:
            self.groups.remove(group)

            self.logger.log(
                "Leaving group {name}#{group}".format(name=name, group=group))
            
            self.consumer.queue_unbind(
                self.exchange_class,
                self.uid,
                "{name}#{group}".format(name=name, group=group)
            )
