Postage - a Python library for AMQP-based network components
============================================================

|Build Status| |Version| |PyPi Downloads|

Postage is a Python library which leverages
`pika <https://github.com/pika/pika>`__ and AMQP (through a broker like
`RabbitMQ <http://www.rabbitmq.com/>`__) to build network-aware software
components.

Through **pika** you can add to any Python program the capability of
sending and receiving messages using AMQP. For example you can listen or
communicate with other programs through a RabbitMQ cluster (The
reference AMQP broker in this documentation is RabbitMQ).

Postage is a layer built on pika, and aims to simplify the
implementation of the messaging part in your Python programs, hiding (as
much as possible) the AMQP details. it provides the following structures
and concepts:

-  **Fingerprint**: an automatic network fingerprint for an application,
   which contains useful data to uniquely identify your program on the
   cluster.

-  **Message encoding** implemented in a stand-alone class which can
   easily be replaced by one of your choice. Default encoding is JSON.

-  A **message** implementation based on a plain Python dictionary (thus
   usable even without Postage). Messages can be of three types:
   **command**, **status** or **result**, representing the actions of
   asking something (command), communicating something (status) or
   answering a request (result). Command messages can be fire-and-forget
   or RPC. Result messages can further transport a success, an error, or
   a Python exception.

-  **Exchanges** can be declared and customized inheriting a dedicated
   class.

-  A generic message **producer** class: it simplifies the definition of
   a set of messages an exchange accepts, which helps in defining a
   network API of your component.

-  A generic message consumer, or **processor**, that implements a
   powerful handlers mechanism to define which incoming messages a
   component is interested in and how it shall answer.

About microthreads
==================

Postage leverages a microthread library to run network components. The
current implementation is very simple and largely underused, due to the
blocking nature of the pika adapter being used. Future plans include a
replacement with a more powerful library. This implementation is a good
starting point if you want to understand generator-based microthreads
but do not expect more. You can read this series of articles
`here <http://lgiordani.github.io/blog/2013/03/25/python-generators-from-iterators-to-cooperative-multitasking/>`__
to begin digging in the matter.

About versioning
================

This is Postage version 1.0.1.

This library is versioned with a A.B.C schema ( **A**\ PI, **B**\ OOST,
**C**\ OMPLAINT ).

-  Any change in the COMPLAINT number is a bugfix or even a typo
   correction in the documentation; it is transparent to running systems
   (except that hopefully *that nasty bug* is no more there).
-  Any change in the BOOST number is an API addition. It is transparent
   to running systems, but you should check the changelog to check
   what's new, perhaps *that impossible thing* is now easy as pie.
-  Any change in the API number has to be taken very seriously. Sorry
   but for some reason the API changed, so your running code will no
   more work.

So update to 1.0.x without hesitation, await the full-of-features 1.1.0
release and beware of the frightening version 2.0.0 that will crash your
systems! =)

[The code contained in the *master* branch on GitHub before the PyPI
release was marked with version 3.0.x. Indeed that is the real version
of the package but since previous versions were not released I wanted to
be a good releaser and start from version 1]

License
=======

This package, Postage, a Python library for AMQP-based network
components, is licensed under the terms of the GNU General Public
License Version 2 or later (the "GPL"). For the GPL 2 please see
LICENSE-GPL-2.0.

Contributing
============

Any form of contribution is highly welcome, from typos corrections to
code patches. Feel free to clone the project and send pull requests.

Quick start
===========

You can find the source code for the following examples in the
``demos/`` directory.

A basic echo server
-------------------

Let's implement a basic echo server made of two programs. The first sits
down and waits for incoming messages with the ``'echo'`` key, the second
sends one message each time it is run.

Be sure to have a running RabbitMQ system configured with a ``/``
virtual host and a ``guest:guest`` user/password.

The file ``echo_shared.py`` contains the definition of the exchange in
use

.. code:: python

    from postage import messaging


    class EchoExchange(messaging.Exchange):
        name = "echo-exchange"
        exchange_type = "direct"
        passive = False
        durable = True
        auto_delete = False

The class attributes are the standard paramenters of AMQP exchanges, see
``exchange_declare()`` in Pika
`documentation <https://pika.readthedocs.org/en/0.9.13/modules/adapters/blocking.html#pika.adapters.blocking_connection.BlockingChannel.exchange_declare>`__.

The file ``echo_send.py``\ defines a message producer and uses it to
send a message

.. code:: python

    from postage import messaging
    import echo_shared


    class EchoProducer(messaging.GenericProducer):
        eks = [(echo_shared.EchoExchange, 'echo-rk')]

    producer = EchoProducer()
    producer.message_echo("A test message")

The producer has two goals: the first is to **define the standard
exchange and routing key used to send the messages**, which prevents you
from specifying both each time you send a message. The second goal is to
**host functions that build messages**; this is an advanced topic, so it
is discussed later.

In this simple case the producer does all the work behind the curtain
and you just need to call ``message_echo()`` providing it as many
parameters as you want. The producer creates a command message named
``'echo'``, packs all ``*args`` and ``**kwds`` you pass to the
``message_echo()`` method inside it, and sends it through the AMQP
network.

The file ``echo_receive.py`` defines a message processor that catches
incoming command messages named ``'echo'`` and prints their payload.

.. code:: python

    from postage import microthreads
    from postage import messaging
    import echo_shared


    class EchoReceiveProcessor(messaging.MessageProcessor):
        @messaging.MessageHandler('command', 'echo')
        def msg_echo(self, content):
            print content['parameters']

    eqk = [(echo_shared.EchoExchange, [('echo-queue', 'echo-rk'), ])]

    scheduler = microthreads.MicroScheduler()
    scheduler.add_microthread(EchoReceiveProcessor({}, eqk, None, None))
    for i in scheduler.main():
        pass

The catching method is arbitrarily called ``msg_echo()`` and decorated
with ``MessageHandler``, whose parameters are the type of the message
(``command``, that means we are instructing a component to do something
for us), and its name (``echo``, automatically set by calling the
``message_echo()`` method). The ``msg_echo()`` method must accept one
parameter, besides ``self``, that is the content of the message. The
content is not the entire message, but a dictionary containing only the
payload; in this case, for a generic ``command`` message, the payload is
a dictionary containing only the ``parameters`` key, that is

Seems overkill? Indeed, for such a simple application, it is. The
following examples will hopefully show how those structures heavily
simplify complex tasks.

To run the example just open two shells, execute
``python echo_receive.py`` in the first one and ``python echo_send.py``
in the second. If you get a
``pika.exceptions.ProbableAuthenticationError`` exception please check
the configuration of the RabbitMQ server; you need to have a ``/``
virtual host and the ``guest`` user shall be active with password
``guest``.

An advanced echo server
-----------------------

Let's add a couple of features to our basic echo server example. First
of all we want to get information about who is sending the message. This
is an easy task for Fingerprint objects

.. code:: python

    from postage import messaging
    import echo_shared


    class EchoProducer(messaging.GenericProducer):
        eks = [(echo_shared.EchoExchange, 'echo-rk')]


    fingerprint = messaging.Fingerprint('echo_send', 'application').as_dict()
    producer = EchoProducer(fingerprint)
    producer.message_echo("A single test message")
    producer.message_echo("A fanout test message", _key='echo-fanout-rk')

As you can see a Fingerprint just needs the name of the application
(``echo_send``) and a categorization (``application``), and
automatically collect data such as the PID and the host. On receiving
the message you can decorate the receiving function with
``MessageHandlerFullBody`` to access the fingerprint

.. code:: python

    @messaging.MessageHandlerFullBody('command', 'echo')
    def msg_echo_fingerprint(self, body):
        print "Message fingerprint: %s", body['fingerprint']

The second thing we are going to add is the ability to send fanout
messages. When you connect to an exchange you can do it with a shared
queue, i.e. a queue declared with the same name by all the receivers, or
with a private queue, that is a unique queue for each receiver. The
first setup leads to a round-robin consumer scenario, with the different
receivers picking messages from the same queue in turn. The second
setup, on the other hand, makes all the receivers get the same message
simultaneously, acting like a fanout delivery.

The file ``echo_shared.py`` does not change, since the Exchange has the
same difinition. In ``echo_receive.py`` we make the greatest number of
changes

::

    from postage import microthreads
    from postage import messaging
    import echo_shared


    class EchoReceiveProcessor(messaging.MessageProcessor):
        def __init__(self, fingerprint):
            shared_queue = 'echo-queue'
            private_queue = 'echo-queue-{0}{1}'.format(fingerprint['pid'],
                                                       fingerprint['host'])

            eqk = [
                (echo_shared.EchoExchange, [
                    (shared_queue, 'echo-rk'),
                    (private_queue, 'echo-fanout-rk')
                ]),
            ]
            super(EchoReceiveProcessor, self).__init__(fingerprint,
                                                       eqk, None, None)

        @messaging.MessageHandler('command', 'echo')
        def msg_echo(self, content):
            print content['parameters']

        @messaging.MessageHandlerFullBody('command', 'echo')
        def msg_echo_fingerprint(self, body):
            print "Message fingerprint: %s", body['fingerprint']


    fingerprint = messaging.Fingerprint('echo_receive', 'controller').as_dict()

    scheduler = microthreads.MicroScheduler()
    scheduler.add_microthread(EchoReceiveProcessor(fingerprint))
    for i in scheduler.main():
        pass

As you can see the ``EchoReceiveProcessor`` redefines the ``__init__()``
method to allow passing just a Fingerprint; as a side-effect, ``eqk`` is
now defined inside the method, but its nature does not change. It
encompasses now two queues for the same exchange; the first queue is
chared, given that every instance of the reveiver just names it
``echo-queue``, while the second is private because the name changes
with the PID and the host of the current receiver, and those values
together are unique in the cluster.

So we expect that sending messages with the ``echo`` key will result in
hitting just one of the receivers at a time, in a round-robin fashion,
while sending messages with the ``echo-fanout`` queue will reach every
receiver.

We defined two different functions to process the incoming ``echo``
message, ``msg_echo()`` and ``msg_echo_fingerprint``; this shows that
multiple functions can be set as handler for the same messages. In this
simple case the two functions could also be merged in a single one, but
sometimes it is better to separate the code of different
functionalities, not to mention that the code could also be loaded at
run-time, through a plugin system or a live definition.

An RPC echo server
------------------

The third version of the echo server shows how to implement RPC
messaging. As before the exchange does not change its signature, so
``echo_shared.py`` remains the same. When sending the message we must
specify the we want to send the RPC form using ``rpc_echo()`` instead of
``message_echo()``

.. code:: python

    from postage import messaging
    import echo_shared

    class EchoProducer(messaging.GenericProducer):
        eks = [(echo_shared.EchoExchange, 'echo-rk')]

    fingerprint = messaging.Fingerprint('echo_send', 'application').as_dict()
    producer = EchoProducer(fingerprint)

    reply = producer.rpc_echo("RPC test message")
    if reply:
        print reply.body['content']['value']
    else:
        print "RPC failed"

Remember that RPC calls are blocking, so your program will hang at the
line ``reply = producer.rpc_echo("RPC test message")``, waiting for the
server to answer. Once the reply has been received, it can be tested and
used as any other message; Postage RPC can return success, error or
exception replies, and their content changes accordingly.

.. code:: python

    from postage import microthreads
    from postage import messaging
    import echo_shared


    class EchoReceiveProcessor(messaging.MessageProcessor):
        def __init__(self, fingerprint):
            eqk = [
                (echo_shared.EchoExchange, [
                                ('echo-queue', 'echo-rk'),
                                ]), 
                ]
            super(EchoReceiveProcessor, self).__init__(fingerprint, eqk, None, None)


        @messaging.RpcHandler('command', 'echo')
        def msg_echo(self, content, reply_func):
            print content['parameters']
            reply_func(messaging.MessageResult("RPC message received"))
            


    fingerprint = messaging.Fingerprint('echo_receive', 'controller').as_dict()

    scheduler = microthreads.MicroScheduler()
    scheduler.add_microthread(EchoReceiveProcessor(fingerprint))
    for i in scheduler.main():
        pass

The receiver does not change severely; you just need to change the
handler dadicated to the incoming ``echo`` message. The decorator is now
``RpcHandler`` and the method must accept a third argument, that is the
function that must be called to answer the incoming message. You have to
pass this function a suitable message, i.e. a ``MessageResult`` if
successfull, other messages to signal an error or an exception. Please
note that after you called the reply function you can continue executing
code.

API Documentation
=================

Here you find a description of the messaging part of Postage. Being
Postage based on AMQP, this help presumes you are familiar with
structures defined by this latter (exchanges, queues, bindings, virtual
hosts, ...) and that you already have a working messaging system (for
example a RabbitMQ cluster).

In the code and in the following text you will find the two terms
"application" and "component" used with the same meaning: a Python
executable which communicates with others using AMQP messages through
Postage. Due to the nature of AMQP you can have components written in
several languages working together: here we assumer both producers and
consumers are written using Postage, but remember that you can make
Postage components work with any other, as far as you stick to its
representation of messages (more on that later).

Environment variables
---------------------

Postage reads three environment variables, ``POSTAGE_VHOST``,
``POSTAGE_USER``, and ``POSTAGE_PASSWORD``, which contain the RabbitMQ
virtual host in use, the user name and the password. The default values
for them are ``/``, ``guest``, ``guest``, i.e. the default values you
can find in a bare RabbitMQ installation. Previous versions used
``POSTAGE_RMQ_USER`` and ``POSTAGE_RMQ_PASSWORD``, which are still
supported but deprecated.

Using the environment variables, especially ``POSTAGE_VHOST``, you can
easily setup production and development environment and to switch you
just need to set the variable before executing your Python components

.. code:: sh

    POSTAGE_VHOST=development mycomponent.py

You obviously need to configure RabbitMQ according to your needs,
declaring the virtual hosts you want.

Setting up separate environment enables your components to exchange
messages without interfering with the production systems, thus avoiding
you to install a separate cluster to test software. The HUP acronym is
used somewhere in the code to mean Host, User, Password, that is the
tuple needed to connect to RabbitMQ plus the virtual host.

A last environment variable, ``POSTAGE_DEBUG_MODE``, drives the debug
output if set to ``true``. It is intended for Postage debugging use
only, since its output is pretty verbose.

Fingerprint
-----------

When componentized system become large you need a good way to identify
your components, so a simple ``Fingerprint`` object is provided to
encompass useful values, which are:

-  ``name``: the name of the component or executable
-  ``type``: a rough plain categorization of the component
-  ``pid``: the OS pid of the component executable
-  ``host``: the host the component is running on
-  ``user``: the OS user running the component executable
-  ``vhost``: the RabbitMQ virtual host the component is running on

This object is mainly used to simplify the management of all those
values, and to allow writing compact code. Since Postage messages are
dictionaries (see below) the object provides a ``as_dict()`` method to
return its dictionary form, along with a ``as_tuple()`` method to
provide the tuple form.

You can use any class to encompass the values you need to identify your
components: Postage ALWAYS uses the dictionary form of fingerprints, so
you need a way to give a meaningful dictionary representation of your
class of choice.

Obviously to uniquely identify a component on a network you need just
host and pid values, but a more complete set of values can greatly
simplify management.

Fingerprint objects can automatically retrieve all values from the OS,
needing only the name and type values; if not passed those are ``None``.

.. code:: python

    fingerprint = Fingerprint(name="mycomponent")
    print fingerprint.as_dict()

Encoder
-------

Postage messages are Python dictionaries serialized in JSON. The
``JsonEncoder`` object provides the ``encode()`` and ``decode()``
methods and the correct type ``application/json``. Encoder class can be
easly replaced in your components, provided that it sticks to this
interface.

Messages
--------

To manage the different types of messages, appropriate objects have been
defined. The base object is ``Message``: it has a **type**, a **name**
and a **category**. It can encompass a **fingerprint** and a
**content**, which are both dictionaries.

The type of the message is free, even if some have been already defined
in Postage: **command**, **status**, and **result**. This categorization
allows the consumers to filter incoming messages according to the action
they require.

The category of the message is not free, and must be one of **message**
and **rpc** (this nomenclature is somewhat misleading, since RPC are
messages just like the standard ones; future plans include a review of
it). The first type marks fire-and-forget messages, while the second
signals RPC ones.

The dictionary form of the message is the following:

.. code:: python

    message = {
        'type': message_type,
        'name': message_name,
        'category': message_category,
        'version': '2',
        'fingerprint': {...},
        'content': {...},
        '_reserved': {...}
        }

The ``content`` key contains the actual data you put in your message,
and its structure is free.

**Command** messages send a command to another component. The command
can be a fire-and-forget one or an RPC call, according to the message
category; the former is implemented by the ``MessageCommand`` class,
while the latter is implemented by ``RpcCommand``. Both classes need the
name of the command and an optional dictionary of parameters, which are
imposed by the actual command. The message fingerprint can be set with
its ``fingerprint(**kwds)`` method.

.. code:: python

        m = messaging.MessageCommand('sum', parameters={a=5, b=6})
        f = Fingerprint(name='mycomponent')
        m.fingerprint(f.as_dict())

**Status** messages bear the status of an application, along with the
application fingerprint. The class which implements this type is
``MessageStatus``. This object needs only a single parameter, which is
the status itself. Not that as long as the status is serializable, it
can be of any nature.

.. code:: python

        m = messaging.MessageStatus('online')

**Result** messages contain the result of an RPC call: three classes
have this type, ``MessageResult``, ``MessageResultError``,
``MessageResultException``. The first is the result of a successful
call, the second is the result of an error in a call, while the third
signals that an exception was raised by the remote component. This error
classification has been inspired by Erlang error management, which I
find a good solution. All three classes contain a **value** and a
**message**, but for errors the value is ``None`` and for exceptions it
is the name of the Python exception.

.. code:: python

        try:
            result = some_operation()
            m = messaging.MessageResult(result)
        except Exception as exc:
            m = messaging.MessageResultException(exc.__class__.__name__, exc.__str__())

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

When you use AMQP you are free to use any format for your messages and
any protocol for sending and receiving data. Postage gives you a
predefined, though extensible, message format, the ``Message`` object.
Moreover, through ``GenericProducer``, it gives you a way to easily
define an API, i.e. a set of shortcut functions that create and send
messages, through which you can interact with your system.

To better introduce the simplification implemented by
``GenericProducer`` let us recap what a component shall do to send a
message using pika and the ``Message`` object.

1. a ``Message`` object has to be declared and filled with the
   information we want to send, according to a given predefined format
   (the message API of our system). The message must contain the correct
   fingerprint and be encoded using the encoder of your choice (choice
   that must be shared by all other components in the system).

2. A connection to the AMQP broker must be established, then all the
   target exchanges must be declared.

3. For each exchange you want to receive the message you shall publish
   it giving the correct routing key for that exchange: the keys you can
   use are part of your messaging API, so you have to "document" them
   when you publish the specification for your exchanges.

As you can see this can quickly lead to a bunch o repeated code, as the
set of operation you need are often the same or very similar; moreover,
it needs a source of documentation outside the code, that is, the API
does not document itself (here I mean: there is no way to get a grasp on
the set of messages you are defining in your API).

Let us see how ``GenericProducer`` solves these issues. First of all you
need to define an exchange:

.. code:: python

    class LoggingExchange(messaging.Exchange):
        name = logging-exchange"
        exchange_type = "direct"
        passive = False
        durable = True
        auto_delete = False

Then you need to define a producer, i.e. an object that inherits from
``GenericProducer``:

.. code:: python

    class LoggingProducer(messaging.GenericProducer):
        pass

since the aim of the producer is that of simplify sending messages to an
exchange you can here specify a set of exchanges/key couples (EKs) which
will be used by default (more on this later).

.. code:: python

    class LoggingProducer(messaging.GenericProducer):
        eks = [(LoggingExchange, 'log')]

Now you have to define a function that builds a ``Message`` containing
the data you want to send

.. code:: python

    class LoggingProducer(messaging.GenericProducer):
        eks = [(LoggingExchange, "log")]
        
        def build_message_status_online(self):
            return messaging.MessageStatus('online')

This allows you to write the following code

.. code:: python

    producer = LoggingProducer()
    producer.message_status_online()

which will build a ``MessageStatus`` containing the ``'online'`` status
string and will send it to the exchange named ``logging-exchange`` with
``'log'`` as routing key.

Magic methods
~~~~~~~~~~~~~

As you can see ``GenericProducer`` automatically defines a
``message_name()`` method that wraps each of the
``build_message_name()`` methods you defines. The same happens with RPC
messages, where the ``rpc_name()`` method is automatically created to
wrap ``build_rpc_name()``.

``message_*()`` methods accept two special keyword arguments, namely
***key\ **, ***\ eks**, that change the way the message is sent. The
behaviour of the two keywords follows the following algorithm:

1. Calling ``message_name()`` sends the message with the predefined
   ``eks``, i.e. those defined in the producer class. This means that
   the message is sent to each exchange listed in the ``eks`` list of
   the class, with the associated key.

2. Calling ``message_name(_key='rk')`` sends the message to the first
   exchange in ``eks`` with the key ``rk``.
3. Calling ``message_name(_eks=[(exchange1, rk1), (exchange2, rk2)])``
   uses the specified eks instead of the content of the default ``eks``
   variable; in this case sends the message to ``exchange1`` with
   routing key ``rk1`` and to ``exchange2`` with routing key ``rk2``.

If you speficy both ``_eks`` and ``_key`` the latter will be ignored.
This system allows you to specify a default behaviour when writing the
producer and to customize the routing key or even the exchange on the
fly.

RPC messages accept also ``_timeout`` (seconds), ``_max_retry`` and
``_queue_only`` to customize the behaviour of the producer when waiting
for RPC answers (more on that later).

Fingerprint
~~~~~~~~~~~

When a ``GenericProducer`` is instanced a ``Fingerprint`` in its
dictionary form can be passed as argument and this is included in each
message object the producer sends. If not given, a bare fingerprint is
created inside the object.

.. code:: python

    f = Fingerprint(name='mycomponent')
    producer = LoggingProducer(fingerprint=f.as_dict())
    producer.message_status_online()

Generic messages
~~~~~~~~~~~~~~~~

You can use a producer to send generic messages using the ``message()``
method

.. code:: python

    p = messaging.GenericProducer()
    p.message(1, "str", values={1, 2, 3, "numbers"},
        _eks=[(MyExchangeCls, "a_routing_key")])

RPC calls
~~~~~~~~~

RPC calls are blocking calls that leverage a very simple mechanism: the
low level AMQP message is given a (usually temporary and private) queue
through its ``reply_to`` property, and this is explicitely used by the
receiver to send an answer.

In Postage an RPC message is defined by a ``build_rpc_name()`` method in
a ``GenericProducer`` and called with ``rpc_name()``; it returns a
result message as sent by the component that answered the call and thus
its type should be one of ``MessageResult``, ``MessageResultError`` or
``MessageResultException`` for plain Postage.

RPC messages accept the following parameters: ``_timeout`` (the message
timeout, defaults to 30 seconds), ``_max_retry`` (the maximum number of
times the message shall be sent again when timing out, default to 4),
and ``_queue_only`` (the call returns the temporary queue on which the
answer message will appear, instead of the message itself).

When the maximum number of tries has been reached the call returns a
``MessageResultException`` with the ``TimeoutError`` exception.

GenericConsumer
---------------

The ``GenericConsumer`` class implements a standard AMQP consumer, i.e.
an object that can connect to exchanges through queues and fetch
messages.

A class that inherits from ``GenericConsumer`` shall define an ``eqk``
class attribute which is a list of tuples in the form
``(Exchange, [(Queue, Key), (Queue, Key), ...])``; each tuple means that
the given exchange will be subscribed by the listed queues, each of them
with the relative routing key.

.. code:: python

    class MyConsumer(GenericConsumer):
        eqk = (
            PingExchage, [('ping_queue', 'ping_rk')],
            LogExchange, [('log_queue', 'log')]
            )

Apart from declaring bindings in the class you can use the
``queue_bind()`` method that accept an exchange, a queue and a key. This
can be useful if you have to declare queues at runtime or if parameters
such as routing key depend on some value you cannot access at
instantiation time.

MessageProcessor
----------------

``MessageProcessor`` objects boost ``GenericConsumer`` to full power =)
A ``MessageProcessor`` is a ``MicroThread`` with two main attributes:
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

Default handlers
~~~~~~~~~~~~~~~~

``MessageProcessor`` objects define two default message handlers to
process incoming command ``quit`` and command ``restart``. The first, as
you can easily guess from the name, makes the component quit; actually
it makes the consumer stop consuming messages and the microthread quit,
so the program executes the code you put after the scheduler loop. If
you put no code, the program just exits. The second command makes the
component restart, i.e. it replaces itself with a new execution of the
same program. This makes very easy to update running systems; just
replace the code and send a ``restart`` to your components.

Credits
~~~~~~~

First of all I want to mention and thank the `Erlang <www.erlang.org>`__
and `RabbitMQ <www.rabbitmq.com>`__ teams and the maintainer of
`pika <https://github.com/pika/pika>`__, Gavin M. Roy, for their hard
work, and for releasing such amazing pieces of software as open source.

Many thanks to `Jeff Knupp <http://www.jeffknupp.com/about-me/>`__ for
his post `Open Sourcing a Python Project the Right
Way <http://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/>`__
and to `Audrey M. Roy <http://www.audreymroy.com/>`__ for her
`cookiecutter <https://github.com/audreyr/cookiecutter>`__ and
`cookiecutter-pypackage <https://github.com/audreyr/cookiecutter-pypackage>`__
tools. All those things make Python packaging a breeze.

.. |Build Status| image:: https://travis-ci.org/lgiordani/postage.png?branch=master
   :target: https://travis-ci.org/lgiordani/postage
.. |Version| image:: https://badge.fury.io/py/postage.png
   :target: http://badge.fury.io/py/postage
.. |PyPi Downloads| image:: https://pypip.in/d/postage/badge.png
   :target: https://crate.io/packages/postage?version=latest
