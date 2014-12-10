from __future__ import print_function

import os
import pika
import json
import functools
import getpass
import sys
import socket
import time
import traceback
import collections
import copy

import microthreads

try:
    global_vhost = os.environ['POSTAGE_VHOST']
except KeyError:
    global_vhost = '/'

try:
    global_user = os.environ['POSTAGE_USER']
except KeyError:
    global_user = 'guest'

try:
    global_password = os.environ['POSTAGE_PASSWORD']
except KeyError:
    global_password = 'guest'

if 'POSTAGE_DEBUG_MODE' in os.environ and \
        os.environ['POSTAGE_DEBUG_MODE'].lower() == 'true':
    debug_mode = True
else:
    debug_mode = False

# Just a simple log to remember the virtual host we are using
if debug_mode:
    print("postage.messaging: global_vhost set to {0}".format(global_vhost))

# This is the default HUP (Host, User, Password)
global_hup = {
    'host': 'localhost',
    'user': global_user,
    'password': global_password
}


class FilterError(Exception):

    """This exception is used to signal that a filter encountered some 
    problem with the incoming message."""
    pass


class Fingerprint(object):

    """The fingerprint of a component.
    This class encompasses all the values the library uses to identify the
    component in the running system.
    """

    def __init__(self, name=None, type=None, pid=os.getpid(),
                 host=socket.gethostname(), user=getpass.getuser(),
                 vhost=global_vhost):
        self.name = str(name)
        self.type = str(type)
        self.pid = str(pid)
        self.host = str(host)
        self.user = str(user)
        self.vhost = str(vhost)

    def as_dict(self):
        return {'name': self.name, 'type': self.type, 'pid': self.pid,
                'host': self.host, 'user': self.user, 'vhost': self.vhost}

    def as_tuple(self):
        return (self.name, self.type, self.pid, self.host,
                self.user, self.vhost)


class Encoder(object):

    """The base message encoder.
    An encoder knows how to encode and decode messages
    to plain strings which can be delivered by AMQP.
    """

    content_type = ""

    @classmethod
    def encode(self, data):
        """Encodes data to a plain string.

        :param data: a Python object
        :type data: object

        """
        return data

    @classmethod
    def decode(self, string):
        """Dencodes data from a plain string.

        :param string: a plain string previously encoded
        :type data: string

        """

        return string


class JsonEncoder(Encoder):

    """A simple JSON encoder and decoder"""

    content_type = "application/json"

    @classmethod
    def encode(self, data):
        return json.dumps(data)

    @classmethod
    def decode(self, string):
        return json.loads(string)


class RejectMessage(ValueError):

    """This exception is used to signal that one of the filters
    rejected the message"""
    pass


class AckAndRestart(ValueError):

    """This exception is used to signal that the message must be acked
    and the application restarted"""
    pass


class Message(object):

    """This class is the base Postage message.
    Message type can be 'command', 'status' or 'result'. Command messages
    transport a command we want to send to a component, either a direct one or
    an RPC one. Status messages transport the status of an application. Result
    messages transport the result of an RPC.
    Message category tells simple commands ('message') from RPC ('rpc'). The
    nomenclature is a little confusing, due to historical reasons (the standard
    excuse to cover bad choices).
    A message has also a boolean representation, through boolean_value.
    The payload of a message can be found inside the 'content' key of the
    message 'body' attribute.
    """
    type = 'none'
    name = 'none'
    category = 'message'
    boolean_value = True

    def __init__(self, *args, **kwds):
        self.body = {}
        self.body['type'] = self.type
        self.body['name'] = self.name
        self.body['category'] = self.category
        self.body['version'] = '2'
        self.body['fingerprint'] = {}
        self.body['content'] = {}
        if len(args) != 0:
            self.body['content']['args'] = args
        if len(kwds) != 0:
            self.body['content']['kwds'] = kwds
        self.body['_reserved'] = {}

    def __unicode__(self):
        return unicode(self.body)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __eq__(self, msg):
        return self.body == msg.body

    def __nonzero__(self):
        return self.boolean_value

    def fingerprint(self, **kwds):
        self.body['fingerprint'].update(kwds)


class MessageCommand(Message):

    """The base implementation of a command message.
    """
    type = 'command'

    def __init__(self, command, parameters={}):
        super(MessageCommand, self).__init__()
        self.body['name'] = str(command)
        self.body['content']['parameters'] = parameters


class RpcCommand(MessageCommand):

    """The base implementation of an RPC message.
    This is exactly the same as a standard cammand message. This is implemented
    in a custom class to allow us to tell apart which messages need an answer.
    """
    type = 'command'
    category = 'rpc'


class MessageStatus(Message):

    """Status of a component.
    A component which wants to send its status to another component
    can leverage this type of message. It adds to the content the
    key name (the name of the message, which is the status itself)
    and application, which is another dictionary containing the following
    information on the component: name, type, pid, host, user, vhost. These six
    values are the standard values a component carries around. Here type has
    nothing to do with messages, but represents a classification of the
    component sending the status.
    """
    type = 'status'

    def __init__(self, status):
        super(MessageStatus, self).__init__()
        self.body['name'] = str(status)


class MessageResult(Message):

    """Result of an RPC call.
    This type of message adds the follwing keys to the message content: type
    (the type of result - success, error of exception), value (the Python value
    for the result) and message (another good naming choice: a string
    describing the result).
    Results can be of three type: success represents a successful call, error
    represents something that can be forecasted when the code of the call has
    been written, and shall be documented, while exception is a Python
    which happened in the remote executor. This error classification has been
    inspired by Erlang error management, which I find a good solution.
    """
    type = 'result'
    result_type = 'success'

    def __init__(self, value, message=''):
        super(MessageResult, self).__init__()
        self.body['content']['type'] = self.result_type
        self.body['content']['value'] = value
        self.body['content']['message'] = message


class MessageResultError(MessageResult):
    type = 'result'
    result_type = 'error'
    boolean_value = False

    def __init__(self, message):
        super(MessageResultError, self).__init__(None, message)


class MessageResultException(MessageResult):
    type = 'result'
    result_type = 'exception'
    boolean_value = False

    def __init__(self, name, message):
        super(MessageResultException, self).__init__(name, message)


class TimeoutError(Exception):

    """An exception used to notify a timeout error while
    consuming from a given queue"""


class ExchangeType(type):

    """A metaclass to type exchanges.
    This allows us to declare exchanges just by setting class attributes.
    Exchanges can then be used without instancing the class.
    """
    def __init__(cls, name, bases, dic):
        super(ExchangeType, cls).__init__(name, bases, dic)
        cls.parameters = {"exchange": cls.name,
                          "exchange_type": cls.exchange_type,
                          "passive": cls.passive,
                          "durable": cls.durable,
                          "auto_delete": cls.auto_delete
                          }


class Exchange(object):

    """A generic exchange.
    This objects helps the creation of an exchange and its use among
    different programs, encapsulating the parameters. Since exchanges can be
    declared again and again an application can always instance
    this object.

    This object has to be inherited and customized.
    """

    __metaclass__ = ExchangeType

    name = "noname"
    exchange_type = "direct"
    passive = False
    durable = True
    auto_delete = False


class GenericProducer(object):

    """A generic class that represents a message producer.
    This class enables the user to implement build_message_*()
    and build_rpc_*() methods and automatically provides the respective
    message_*() and rpc_*() methods that build the message with the
    given parameters, encodes and sends it.

    When a user calls producer.message_test() for example, the producer calls
    build_message_test() to create the message, then calls _message_send()
    to encode and send it

    Encoding can be changed giving the object a custom encoder object.
    The virtual host, the publishing exchange and the routing key can be
    customized with self.vhost, self.exchange and self.routing_key.

    The virtual host has some higher degree of cutomization: it can be
    specified when subclassing the object or when initializing it. The former
    is more appropriate for library objects which can be instanced by many
    components, while the latter is better suited for single instance objects
    or small environments.

    Message can be routed to different exchanges with different routing keys.
    When a message_*() method is called without passing a custom exchange or
    key the ones given as class attributes are used.
    When a message_*() method is called passing the routing key as the '_key'
    parameter the message is sent to the default exchange (the one given as
    class attribute) with that key.
    When a message_*() method is called passing a dictionary '_eks' of
    exchange/keys couples the exchange_class attribute has to be a dictionary
    of exchange names/exchange classses, and the names used sending the message
    shall be in this dictionary. If not the exchange is skipped.

    RPC messages are always sent to the 'default' exchange: that is either the
    only one you specified as class attribute or the one found with that key.
    """

    eks = [(Exchange, "nokey")]
    encoder_class = JsonEncoder
    vhost = global_vhost

    # After this time the RPC call is considered failed
    rpc_timeout = 30

    # The RPC calls is repeated max_retry times
    max_retry = 4

    # Host, User, Password
    hup = global_hup

    def __init__(self, fingerprint={}, hup=None, vhost=None):
        if hup is not None:
            self.hup = hup
        credentials = pika.PlainCredentials(self.hup['user'],
                                            self.hup['password'])
        host = self.hup['host']

        if vhost:
            self.vhost = vhost

        conn_params = pika.ConnectionParameters(host, credentials=credentials,
                                                virtual_host=str(self.vhost))

        self.conn_broker = pika.BlockingConnection(conn_params)

        self.encoder = self.encoder_class()
        self.default_exchange = self.eks[0][0]
        self.fingerprint = Fingerprint().as_dict()
        self.fingerprint.update(fingerprint)

        self.channel = self.conn_broker.channel()
        if debug_mode:
            print("Producer {0} declaring eks {1}".
                  format(self.__class__.__name__, self.eks))
            print
        for exc, key in self.eks:
            self.channel.exchange_declare(**exc.parameters)

    def _build_message_properties(self):
        msg_props = pika.BasicProperties()
        msg_props.content_type = self.encoder.content_type
        return msg_props

    def _build_rpc_properties(self):
        # Standard Pika RPC message properties
        msg_props = pika.BasicProperties()
        msg_props.content_type = self.encoder.content_type
        result = self.channel.queue_declare(exclusive=True, auto_delete=True)
        msg_props.reply_to = result.method.queue
        return msg_props

    def _encode(self, body):
        return json.dumps(body)

    def _get_eks(self, kwds):
        # Extracts a dictionary with Exchange/Key couples from kwds
        # Calling without keys returns self.eks
        # Calling with just _key=k returns [(default_exc, k)]
        # Calling with _key=k and _eks=ek_list returns ek_list
        # Calling with _eks=ek_list returns ek_list
        # where default_exc is the first exchange defined in self.eks
        # and ek_list is in the form
        # [(EXCHANGE, ROUTING_KEY), ...]
        #
        # This allows to call methods with just _key if the exchange is the
        # default one (or the only one) or with a complete EK specification.
        #
        # TODO: I do not like this way of passing values, I'd prefer to
        # leverage function atttributes and decorators. When there is
        # enough time...
        if '_key' in kwds:
            exchange = self.eks[0][0]
            return [(exchange, kwds.pop('_key'))]
        else:
            return kwds.pop('_eks', self.eks)

    def _message_send(self, *args, **kwds):
        eks = self._get_eks(kwds)
        msg_props = self._build_message_properties()

        # TODO: Why is this keyword not passed simply as named argument?
        callable_obj = kwds.pop('_callable')
        message = callable_obj(*args, **kwds)
        message.fingerprint(**self.fingerprint)
        encoded_body = self.encoder.encode(message.body)

        for exchange, key in eks:
            if debug_mode:
                print("--> {name}: basic_publish() to ({exc}, {key})".
                      format(name=self.__class__.__name__,
                             exc=exchange,
                             key=key))
                for _key, _value in message.body.iteritems():
                    print("    {0}: {1}".format(_key, _value))
                print
            self.channel.basic_publish(body=encoded_body,
                                       exchange=exchange.name,
                                       properties=msg_props,
                                       routing_key=key)

    def _rpc_send(self, *args, **kwds):
        eks = self._get_eks(kwds)
        timeout = kwds.pop('_timeout', self.rpc_timeout)
        max_retry = kwds.pop('_max_retry', self.max_retry)
        queue_only = kwds.pop('_queue_only', False)
        callable_obj = kwds.pop('_callable')

        message = callable_obj(*args, **kwds)
        message.fingerprint(**self.fingerprint)
        encoded_body = self.encoder.encode(message.body)

        exchange, key = eks[0]

        _counter = 0
        while True:
            try:
                # TODO: Message shall be sent again at each loop???
                msg_props = self._build_rpc_properties()
                if debug_mode:
                    print("--> {name}: basic_publish() to ({exc}, {key})".
                          format(name=self.__class__.__name__,
                                 exc=exchange,
                                 key=key))
                    for _key, _value in message.body.iteritems():
                        print("    {0}: {1}".format(_key, _value))
                    print
                self.channel.basic_publish(body=encoded_body,
                                           exchange=exchange.name,
                                           properties=msg_props,
                                           routing_key=key)

                if queue_only:
                    return msg_props.reply_to
                else:
                    results = self.consume_rpc(msg_props.reply_to,
                                               timeout=timeout)
                    return results[0]
            except TimeoutError as exc:
                if _counter < self.max_retry:
                    _counter = _counter + 1
                    continue
                else:
                    return MessageResultException(exc.__class__.__name__,
                                                  exc.__str__())

    def message(self, *args, **kwds):
        eks = self._get_eks(kwds)
        msg_props = self._build_message_properties()
        message = Message(*args, **kwds)
        message.fingerprint(**self.fingerprint)
        encoded_body = self.encoder.encode(message.body)

        for exchange, key in eks:
            self.channel.basic_publish(body=encoded_body,
                                       exchange=exchange.name,
                                       properties=msg_props,
                                       routing_key=key)

    def forward(self, body, *args, **kwds):
        eks = self._get_eks(kwds)
        msg_props = self._build_message_properties()
        encoded_body = self.encoder.encode(body)

        for exchange, key in eks:
            self.channel.basic_publish(body=encoded_body,
                                       exchange=exchange.name,
                                       properties=msg_props,
                                       routing_key=key)

    def __getattr__(self, name):
        # This customization redirects message_*() and rpc_*() function calls
        # to _message_send() and _rpc_send() using respectively
        # build_message_*() and build_rpc_*() functions defined in
        # the subclass of this object.
        if name.startswith('message_'):
            command_name = name.replace('message_', '')
            func = 'build_message_' + command_name
            try:
                method = self.__getattribute__(func)
            except AttributeError:
                method = functools.partial(MessageCommand, command_name)
            return functools.partial(self._message_send, _callable=method)
        elif name.startswith('rpc_'):
            command_name = name.replace('rpc_', '')
            func = 'build_rpc_' + command_name
            try:
                method = self.__getattribute__(func)
            except AttributeError:
                method = functools.partial(RpcCommand, command_name)
            return functools.partial(self._rpc_send, _callable=method)
        elif name.startswith('rpc_queue'):
            command_name = name.replace('rpc_queue_', '')
            func = 'build_rpc_' + command_name
            try:
                method = self.__getattribute__(func)
            except AttributeError:
                method = functools.partial(RpcCommand, command_name)
            return functools.partial(self._rpc_send,
                                     _callable=method,
                                     _queue_only=True)

    def consume_rpc(self, queue, result_len=1, callback=None, timeout=None):
        """Consumes an RPC reply.

        This function is used by a producer to consume a reply to an RPC call
        (thus the queue specified in the reply_to header must be specified
        as parameter.

        If a callback callable is given it is called after message has been
        received. The function returns the 'data' part of the reply message
        (a dictionary).
        """

        if timeout is None or timeout < 0:
            timeout = self.rpc_timeout

        result_list = []

        def _callback(channel, method, header, body):
            reply = self.encoder.decode(body)

            try:
                if reply['content']['type'] == 'success':
                    message = MessageResult(reply['content']['value'],
                                            reply['content']['message'])
                elif reply['content']['type'] == 'error':
                    message = MessageResultError(reply['content']['message'])
                elif reply['content']['type'] == 'exception':
                    message = MessageResultException(
                        reply['content']['value'],
                        reply['content']['message'])
                else:
                    raise ValueError
            except (KeyError, ValueError):
                message = MessageResultError("Malformed reply {0}".
                                             format(reply['content']))

            result_list.append(message)
            if callback is not None:
                callback(reply)

            if len(result_list) == result_len:
                channel.stop_consuming()

        def _outoftime():
            self.channel.stop_consuming()
            raise TimeoutError

        tid = self.conn_broker.add_timeout(timeout, _outoftime)
        self.channel.basic_consume(_callback, queue=queue)
        self.channel.start_consuming()
        self.conn_broker.remove_timeout(tid)

        if result_list == []:
            result_list.append(MessageResultError('\
                An internal error occoured to RPC - result list was empty'))
        return result_list

    def serialize_text_file(self, filepath):
        f = file(filepath, 'r')
        result = {}
        result['name'] = os.path.basename(filepath)
        result['content'] = f.readlines()
        return result


class GenericConsumer(object):
    encoder_class = JsonEncoder
    vhost = global_vhost

    # Host, User, Password
    hup = global_hup

    # List of (Exchange, [(Queue, Key), (Queue, Key), ...])
    # Queue may be specified as string (the name of the queue) or
    # as a dictionary {'name':queue_name, 'flags':{'flag1':True,
    # 'flag2':False}}
    eqk = []

    def __init__(self, eqk=[], hup=None, vhost=None):
        if hup is not None:
            self.hup = hup
        credentials = pika.PlainCredentials(self.hup['user'],
                                            self.hup['password'])
        host = self.hup['host']

        if vhost:
            self.vhost = vhost
        conn_params = pika.ConnectionParameters(host, credentials=credentials,
                                                virtual_host=self.vhost)

        self.conn_broker = pika.BlockingConnection(conn_params)

        self.encoder = self.encoder_class()
        self.channel = self.conn_broker.channel()

        if len(eqk) != 0:
            self.eqk = eqk

        self.qk_list = []

        self.add_eqk(self.eqk)

        self.channel.basic_qos(prefetch_count=1)

        # Enabling this flag bypasses the msg_consumer function and just
        # rejects all messages
        self.discard_all_messages = False

    def add_eqk(self, eqk):
        for exchange_class, qk_list in eqk:
            for queue_info, key in qk_list:
                if isinstance(queue_info, collections.Mapping):
                    self.queue_bind(exchange_class,
                                    queue_info['name'],
                                    key,
                                    **queue_info['flags'])
                else:
                    self.queue_bind(exchange_class, queue_info, key)

    def queue_bind(self, exchange_class, queue, key, **kwds):
        if debug_mode:
            print("Consumer {name}: Declaring exchange {e}".
                  format(name=self.__class__.__name__,
                         e=exchange_class))
        self.channel.exchange_declare(**exchange_class.parameters)

        if debug_mode:
            print("Consumer {name}: Declaring queue {q}".
                  format(name=self.__class__.__name__,
                         q=queue))
        self.channel.queue_declare(queue=queue, **kwds)

        if debug_mode:
            print("Consumer {name}: binding queue {q} with exchange {e} with routing key {k}".
                  format(name=self.__class__.__name__,
                         q=queue,
                         e=exchange_class,
                         k=key))
        self.channel.queue_bind(queue=queue, exchange=exchange_class.name,
                                routing_key=key)
        self.qk_list.append((queue, key))

    def queue_unbind(self, exchange_class, queue, key):
        self.channel.exchange_declare(**exchange_class.parameters)
        self.channel.queue_unbind(queue=queue, exchange=exchange_class.name,
                                  routing_key=key)

    def start_consuming(self, callback):
        for queue, key in self.qk_list:
            self.channel.basic_consume(callback, queue=queue)
        self.channel.start_consuming()

    def stop_consuming(self):
        self.channel.stop_consuming()

    def ack(self, method):
        self.channel.basic_ack(delivery_tag=method.delivery_tag)

    def reject(self, method, requeue):
        self.channel.basic_reject(delivery_tag=method.delivery_tag,
                                  requeue=requeue)

    def decode(self, data):
        return self.encoder.decode(data)

    def rpc_reply(self, header, message):
        try:
            encoded_body = self.encoder.encode(message.body)
        except AttributeError:
            msg = MessageResult(message)
            encoded_body = self.encoder.encode(msg.body)

        self.channel.basic_publish(body=encoded_body, exchange="",
                                   routing_key=header.reply_to)


class MessageHandler(object):

    """This decorator takes two parameters: message_type and message_name.
    message_type is the type of message the handler can process
    (e.g. "command", "status") message_name is the actual message name
    Decorating a method with this class marks it so that it is called every
    time a message with that type and name is received.
    """

    def __init__(self, message_type, message_name=None):
        self.handler_data = ("message", message_type, message_name, 'content')

    def __call__(self, func):
        func._message_handler = self.handler_data
        return func


class RpcHandler(MessageHandler):

    """This decorator takes two parameters: message_type and message_name.
    message_type is the type of message the handler can process
    (e.g. "command", "status") message_name is the actual message name
    Decorating a method with this class marks it so that it is called every
    time an RPC with that type and name is received.
    """

    def __init__(self, message_type, message_name=None):
        self.handler_data = ("rpc", message_type, message_name, 'content')

    # def __call__(self, func):
    #     func._message_handler = self.handler_data
    #     return func


class MessageHandlerFullBody(MessageHandler):

    """This decorator behaves the same as MessageHandler but makes the
    decorated method receive the full message body instead the sole content.
    """

    def __init__(self, handler_type, message_name=None):
        self.handler_data = ("message", handler_type, message_name, None)


class Handler(object):
    _message_handler = True

    def __init__(self, processor, data, reply_func=None):
        self.processor = processor
        self.reply_func = reply_func
        self.data = data
        self.call()


class MessageFilter(object):

    """This decorator takes as parameter a callable. The callable must accept
    a message as argument and is executed every time a message is processed
    by the decorated function.

    The callable shall return the filtered message. Any exception will result
    in the message being discarded without passing through the message handler.

    Example:

    def filter_message(message):
        [...]

    @messaging.MessageFilter(filter_message)
    @messaging.MessageHandler('command', 'a_command')
    def a_command(self, content):
        [...]

    When a message is processed by a_command() it is first processed by
    filter_message().

    """

    def __init__(self, _callable, *args, **kwds):
        self.callable = _callable
        self.args = args
        self.kwds = kwds

    def __call__(self, func):
        try:
            func.filters.append((self.callable, self.args, self.kwds))
        except AttributeError:
            func.filters = [(self.callable, self.args, self.kwds)]
        return func


class MessageHandlerType(type):

    """This metaclass is used in conjunction with the MessageHandler decorator.
    An object with this metaclass has an internal dictionary called
    _message_handlers that contains all methods which can process an incoming
    message keyed by message type. The dictionary is filled by the __init__ of
    the metaclass, looking for the attribute _message_handler attached by the
    MessageHandler decorator.
    """
    def __init__(cls, name, bases, attrs):
        try:
            cls._message_handlers
        except AttributeError:
            cls._message_handlers = {}

        for key, method in attrs.iteritems():
            if hasattr(method, '_message_handler'):
                message_category, message_type, message_name, body_key =\
                    method._message_handler

                message_key = (message_category, message_type, message_name)

                if message_key not in cls._message_handlers:
                    cls._message_handlers[message_key] = []

                cls._message_handlers[message_key].append((method, body_key))


class MessageProcessor(microthreads.MicroThread):

    """A MessageProcessor is a MicroThread with MessageHandlerType as
    metaclass. This means that it can be used as a microthred in a scheduler
    and its methods can be decorated with the MessageHandler decorator.
    Two standard message handler are available ('command', 'quit') and
    ('command', 'restart'). The _msg_consumer() method loops over message
    handlers to process each incoming message.
    """

    consumer_class = GenericConsumer
    __metaclass__ = MessageHandlerType

    def __init__(self, fingerprint, eqk, hup, vhost):
        # This is a generic consumer, customize the consumer_class class
        # attribute with your consumer of choice
        self.consumer = self.consumer_class(eqk, hup, vhost)
        self.fingerprint = fingerprint

    def add_eqk(self, eqk):
        self.consumer.add_eqk(eqk)

    def add_timeout(self, seconds, callback=None):
        if callback is not None:
            self.consumer.conn_broker.add_timeout(seconds, callback)
        else:
            self.consumer.conn_broker.sleep(seconds)

    @MessageHandler('command', 'quit')
    def msg_quit(self, content):
        self.consumer.stop_consuming()
        raise microthreads.ExitScheduler

    @MessageHandler('command', 'restart')
    def msg_restart(self, content):
        self.consumer.stop_consuming()
        raise AckAndRestart

    def restart(self):
        executable = sys.executable
        os.execl(executable, executable, *sys.argv)

    def _filter_message(self, callable_obj, message_body):
        filtered_body = {}
        filtered_body.update(message_body)

        try:
            for _filter, args, kwds in callable_obj.filters:
                try:
                    filtered_body = _filter(filtered_body, *args, **kwds)
                except FilterError as exc:
                    if debug_mode:
                        print("Filter failure")
                        print("  Filter:", _filter)
                        print("  Args:  ", args)
                        print("  Kwds:  ", kwds)
                        print("  Filter message:", exc.args)
                    raise
        except AttributeError:
            pass

        return filtered_body

    def _msg_consumer(self, channel, method, header, body):
        decoded_body = self.consumer.decode(body)

        if debug_mode:
            print("<-- {0}: _msg_consumer()".format(self.__class__.__name__))
            for _key, _value in decoded_body.iteritems():
                print("    {0}: {1}".format(_key, _value))
            print
        try:
            message_category = decoded_body['category']
            message_type = decoded_body['type']
            if message_category == "message":
                message_name = decoded_body['name']

                handlers = self._message_handlers.get((message_category,
                                                       message_type,
                                                       message_name), [])

                for callable_obj, body_key in handlers:
                    # Copies are made to avoid filters change the original
                    # message that could be parsed by other handlers
                    if body_key is None:
                        filtered_body = copy.deepcopy(decoded_body)
                    else:
                        filtered_body = copy.deepcopy(decoded_body[body_key])

                    try:
                        filtered_body = self._filter_message(
                            callable_obj, filtered_body)

                        callable_obj(self, filtered_body)
                    except FilterError:
                        if debug_mode:
                            print("Filter error in handler", callable_obj)
            elif message_category == 'rpc':
                try:
                    reply_func = functools.partial(
                        self.consumer.rpc_reply, header)

                    if message_type == 'command':
                        message_name = decoded_body['name']

                        handlers = self._message_handlers.get((message_category,
                                                               message_type,
                                                               message_name), [])

                        if len(handlers) != 0:
                            callable_obj, body_key = handlers[-1]
                            filtered_body = {}
                            filtered_body.update(decoded_body['content'])

                            try:
                                filtered_body = self._filter_message(
                                    callable_obj, filtered_body)
                                callable_obj(self, filtered_body, reply_func)
                            except FilterError:
                                if debug_mode:
                                    print(
                                        "Filter error in handler", callable_obj)
                except Exception as exc:
                    reply_func(MessageResultException(
                        exc.__class__.__name__, exc.__str__()))
                    raise

            # Ack it since it has been processed - even if no handler
            # recognized it
            self.consumer.ack(method)

        except (microthreads.ExitScheduler, StopIteration):
            self.consumer.ack(method)
            raise
        except RejectMessage:
            self.consumer.reject(method, requeue=False)
        except AckAndRestart:
            self.consumer.ack(method)
            self.restart()
        except Exception as exc:
            print("Unmanaged exception in {0}".format(self))
            print(exc)
            traceback.print_exc()
            self.consumer.reject(method, requeue=False)

        return

    def start_consuming(self):
        self.consumer.start_consuming(callback=self._msg_consumer)

    def stop_consuming(self):
        self.consumer.stop_consuming()

    def step(self):
        self.start_consuming()
