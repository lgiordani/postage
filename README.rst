Postage - a Python library for AMQP-based network components
============================================================

Postage is a Python library which leverages
`pika <https://github.com/pika/pika>`__ and AMQP (through a broker like
`RabbitMQ <http://www.rabbitmq.com/>`__) to simplify building
componentized software.

Python programs can be easily converted to stand-alone components which
communicate through messages; Postage makes the following structures
available to the programmer:

-  Generator-based microthreads (microthreads.py)
-  AMQP message producer and consumers (messaging.py)

Microthreads have been implemented here for historical reasons; future
plans include a replacement with a more paowerful library. This
implementation is a good starting point if you want to understand
generator-based microthreads but do not expect more. You can this series
of articles
`here <http://lgiordani.github.io/blog/2013/03/25/python-generators-from-iterators-to-cooperative-multitasking/>`__
to begin digging in the matter.

In the following documentation, the reference broker is RabbitMQ.

A note about versioning
=======================

This is Postage version 3.0.3.

You will not find here versions prior 3.0.0. They have been used in a
semi-production environment, but their development history is not worth
being released (a good way to cover horrible mistakes made in the past
=) ).

This library is versioned with a A.B.C schema ( **A**\ PI, **B**\ OOST,
**C**\ OMPLAINT ).

-  Any change in the COMPLAINT number is a bugfix or even a typo
   correction; it is transparent to running systems (except that
   hopefully that nasty bug is no more there).
-  Any change in the BOOST number is an API addition. It is transparent
   to running systems, but you should check the changelog to check
   what's new, perhaps that impossible thing is now easy as pie.
-  Any change in the API number has to be taken very seriously. Sorry
   but for some nasty reason the API changed, so your running code will
   no more work.

So beware of the frightening version 4.0.0 that will crash your systems!

License
=======

This package, Postage, is licensed under the terms of the GNU General
Public License Version 2 or later (the "GPL").

Messaging
=========

Here you find a description of the messaging part of Postage. Being
Postage based on AMQP, this help presumes you are familiar with
structures defined by this latter (exchanges, queues, bindings, virtual
hosts, ...) and that you already have a working messaging system (for
example a RabbitMQ cluster).

In the code and in the following text you will find the two terms
"application" and "component" used with the same meaning: a Python
executable which communicates with other using AMQP messages through
Postage.

Environment variables
---------------------

Postage reads three environment variables, ``POSTAGE_VHOST``,
``POSTAGE_RMQ_USER``, and ``POSTAGE_RMQ_PASSWORD``, which contain the
RabbitMQ virtual host in use, the user name and the password. The
default values for them are ``/``, ``guest``, ``guest``, i.e. the
default values you can find in a bare RabbitMQ installation.

Using the environment variables, expecially ``POSTAGE_VHOST`` you can
easily setup production and development environment and to switch you
just need to set the variable before executing your Python components

.. code:: sh

    POSTAGE_VHOST=development mycomponent.py

You obviously need to configure RabbitMQ according to your needs,
declaring the virtual hosts you want.

Setting separate environment enables your components to exchange
messages without interfering with the production systems, thus avoiding
you to install a separate cluster to test software.

The HUP acronym is used somewhere in the code to mean Host, User,
Password, that is the tuple needed to connect to RabbitMQ (plus the
virtual host).

A last environment variable, ``POSTAGE_DEBUG_MODE``, drives the debug
output if set to ``true``. It is intended for Postage debugging use
only, since its output is pretty verbose.

Fingerprint
-----------

When componentized system become large you need a good way to identify
your components, so a simple ``Fingerprint`` object is provided to
encompass useful values, which are: **name** (the name of the component
or executable), **type** (a rough plain categorization of the
component), **pid** (the OS pid of the component executable), **host**
(the host the component is running on), **user** (the OS user running
the component executable), **vhost** (the RabbitMQ virtual host the
component is running on).

This object is mainly used to simplify the use of all those values, and
to allow writing compact code. Since Postage messages are dictionaries
(see below) the object provides a ``as_dict()`` method to return its
dictionary form, along with a ``as_tuple()`` method to provide the tuple
form.

You can use any class to encompass the values you need to identify your
components: Postage ALWAYS uses the dictionary form of fingerprints, so
you shall be sure to be able to give a meaningful dictionary
representation of your class of choice.

Obviously to uniquely identify a component on a network you need just
host and pid values, but a more complete set of values can gratly
simplify management.

Fingerprint objects can retrieve all values from the OS, needing only
the name and type values; if not passed those are ``None``.

Encoder
-------

Postage messages are dictionaries serialized in JSON. The
``JsonEncoder`` object provides the ``encode()`` and ``decode()``
methods and the correct type ``application/json``. Encoder class can be
easly replaced in your components, provided that it sticks to this
interface.

Messages
--------

As already stated the data Postage sends to RabbitMQ are dictionaries
serialized in JSON. To manage the different types of messages, however,
appropriate objects have been defined. The base object is ``Message``:
it has a **type**, a **category**, and a **boolean value**.

The type of the message is free, even if some have been already defined
in Postage: **command**, **status**, and **result**. The category of the
message is not free, and must be one of **message** and **rpc** (this
nomenclature is somewhat misleading, since RPC are messages just like
the standard ones; future plans include a review of it).

The dictionary form of the message is the following:

.. code:: python


    message = {
        'type':message_type,
        'category':message_category,
        'version':2,
        'fingerprint':{...},
        'content':{...},
        '_reserved`:{...}
        }

The ``content`` key contains the actual data you put in your message.

**Command** messages send a command to another component. The command
can be a fire-and\_forget one or an RPC call, accordingto the message
type; the first type is implemented by the ``MessageCommand`` class,
while the second is implemented by ``RpcCommand``. Both classes need the
name of the command, the application fingerprint, and optionally a
dictionary of parameters, which are imposed by the actual command.

**Status** messages bear the status of an application, which is a simple
string, along with the application fingerprint. The class which
implements this type is ``MessageStatus``.

**Result** messages contain the result of an RPC call: three classes
have this type, ``MessageResult``, ``MessageResultError``,
``MessageResultException``. The first is the result of a successful
call, the second is the result of an error in a call, while the third
signals that an exception was raised by the remote component. This error
classification has been inspired by Erlang error management, which I
find a good solution. All three classes contain a **value** and a
**message**, but for errors the value is ``None`` and for exceptions it
is the name of the Python exception.

Exchange
--------

The ``Exchange`` class allows to declare exchanges just by customizing
the class parameters. It provides a ``parameters`` class property that
gives a dictionary representation of the exchange itself, as required by
the ``exchange_declare()`` method of the AMQP channel.

To declare your own exchange you just need to inherit ``Exchange``

.. code:: python

    from postage import messaging
    class MyExchange(messaging.Exchange):
        name = "my-custom-exchange"
        exchange_type = "topic"
        passive = False
        durable = True
        auto_delete = False

GenericProducer
---------------

The ``GenericProducer`` class implements an object that can send
messages to RabbitMQ.

Its main feature is to provide "magic" mathods to send messages. The
programmer must define a ``build_message_NAME()`` (or
``build_rpc_NAME()``) method which returns a ``Message`` object (or
derived) and the instanced object will provide a ``message_NAME()`` (or
``rpc_NAME()``) method that sends the message to RabbitMQ.

The four class attributes ``eks``, ``encoder_class``, ``routing_key``,
and ``vhost`` are used as defaults when sending messages. Virtual host
and HUP can be redefined when deriving the class or when instancing it.

The ``eks`` attribute (the name aims to be the plural of Exchange/Key)
is a list of tuples in the form ``(exchange_name:routing_key)``; the
first exchange in this list is stored as the default exchange and used
for RPC calls.

Magic methods ``message_NAME()`` and ``rpc_NAME()`` accept custom
exchanges and routing keys specified at run-time. Using
``message_NAME()`` as an example (RPC magic methods have the same
syntax) you can use three different forms of call

-  ``message_NAME()`` uses the ``eks`` class attribute.
-  ``message_NAME(_key=KEY)`` uses the default exchange and the given
   routing key to route the message.
-  ``message_NAME(_eks={EXCHANGE_NAME:ROUTING_KEY, ...}) uses the given exchange/keys. This latter form ignores the possible``\ \_key\`
   parameter.

When a ``GenericProducer`` is instanced a ``Fingerprint`` in its
dictionary form can be passed as argument and this is included in each
message object the producer sends.

You can use a producer to send generic messages

.. code:: python

    p = messaging.GenericProducer()
    p.message(1, "str", values={1, 2, 3, "numbers"}, _eks=[(MyExchangeCls, "a_routing_key")])

or inherit it and build a richer object

.. code:: python

    class PingExchange(messaging.Exchange):
        name = "ping-exchange"
        exchange_type = "direct"
        passive = False
        durable = True
        auto_delete = False


    class PingProducer(messaging.GenericProducer):
        eks = [(PingExchange, 'ping')]

        def build_message_ping(self):
            return messaging.MessageCommand('ping', parameters={'send_time':time.time()})

    p = PingProducer()
    p.message_ping()
            

RPC calls are blocking calls that leverage the RPC mechanism of RabbitMQ
(through ``reply_to``). An RPC message is defined by a
``build_rpc_NAME()`` method and called with ``rpc_NAME()``; it returns a
result message as sent by the component that answered the call and thus
its type should be one of MessageResult, MessageResultError or
MessageResultException.

RPC messages accept the following parameters: ``_timeout`` (the message
timeout, defaults to 30 seconds), ``_max_retry`` (the maximum number of
times the message shall be sent again when timing out, default to 4),
and ``_queue_only`` (the call returns the temporary queue on which the
answer message will appear, instead of the message itself).

When timing out the call is automatically retried, but when the maximum
number of tries has been reached the call returns a
``MessageResultException`` with the ``TimeoutError`` exception.

GenericConsumer
---------------

The ``GenericConsumer`` class implements an object that can connect to
exchanges through queues and fetch messages. Recall from RabbitMQ that
you have to declare a queue that subscribes a given exchange with a
given routing key and that queue will automatically receive messages
that match.

The ``GenericConsumer`` derived class shall define an ``eqk`` class
attribute which is a list of tuples in the form
``(Exchange, [(Queue, Key), (Queue, Key), ...])``; each tuple means that
the given exchange will be subscribed by the listed queues, each of them
with the relative routing key.

Apart from declaring bindings in the class you can use the
``queue_bind()`` method that accept an exchange, a queue and a key. This
can be useful if you have to declare queues at runtime or if parameters
such as routing key depend on some value you cannot access at
instantiation time.

MessageProcessor
----------------

``MessageProcessor`` objects leverage ``GenericConsumer`` to full power
=) A ``MessageProcessor`` is a ``MicroThread`` with two main attributes:
``self.consumer`` (a ``GenericConsumer`` or derived class) and a
``self.fingerprint`` (a ``Fingerprint`` in its dictionary form).

Inside a ``MessageProcessor`` you can define a set of methods called
"message handlers" that process incoming messages. The methods can be
freely called and have to be decorated with the ``@MessageHandler``
decorator; this needs two parameters: the type of the message and the
name. So defining

.. code:: python

    @MessageHandler('command', 'quit')
    def msg_quit(self, content):
        [...]

you make the method ``msg_quit()`` process each incoming message which
type is ``command`` and name is ``quit``. You can define as many message
handlers as you want for the same message type/name, but beware that
they are all executed in random order. As you can see from the example a
message handler method must accept a parameter which receives the
content of the processed message.

You can also decorate a method with the ``@RpcHandler`` decorator; in
that case the method must accept two parameters, the first being the
content of the received message, the second a reply function. The method
has the responsibility of calling it passing a ``MessageResult`` or
derived object. This mechanism allows the handler to do some cleanup
after sending the reply.

Message handlers can also be defined as classes inside a
``MessageProcessor`` and have to inherit from ``Handler`` and define a
``call()`` method which accepts only self; it can then access the
``self.data`` and ``self.reply_func`` attributes that contain the
incoming message and the return function. The difference between the
method and class version of the message handlers is that the class
version can access the underlying ``MessageProcessor`` through its
``self.processor`` attribute. This is useful to access the fingerprint
of the message or any other attribute that is included in the processor.
A class is then in general richer thana simple method, thus giving more
freedom to the programmer.

The last available decorator is ``MessageHandlerFullBody`` that passes
to the decorated method or class the full body of the incoming message
instead that only the value of the ``content`` key like
``MessageHandler`` and ``RpcHandler`` do.
