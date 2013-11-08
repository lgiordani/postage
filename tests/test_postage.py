import unittest
import mock
import time

import messaging

test_status_kwds = {'name':'test_name', 'type':'test_type', 'pid':'1234',
            'host':'test_host', 'user':'test_user', 'vhost':'test_vhost'}

class TestStatus(unittest.TestCase):
    def setUp(self):
        self.kwds = dict(test_status_kwds)
        self.status = messaging.Fingerprint(**self.kwds)
        
    def test_dictionary_representation_works(self):
        self.assertEqual(self.status.as_dict(), self.kwds)
        
    def test_tuple_representation_works(self):
        self.assertEqual(self.status.as_tuple(),
            (self.kwds['name'], self.kwds['type'], self.kwds['pid'],
            self.kwds['host'], self.kwds['user'], self.kwds['vhost'], ))


class TestEncoder(unittest.TestCase):
    def setUp(self):
        self.encoder = messaging.Encoder()

    def tearDown(self):
        pass
    
    def test_encoding_and_decoding_returns_the_same_data(self):
        s = {'string':'a simple test dictionary', 'number':4}
        encs = self.encoder.encode(s)
        self.assertEqual(s, self.encoder.decode(encs))


class TestJsonEncoder(TestEncoder):
    def setUp(self):
        self.encoder = messaging.JsonEncoder()
        
    def test_content_type_is_correct(self):
        self.assertEqual(self.encoder.content_type, 'application/json')


class TestMessage(unittest.TestCase):
    boolean_value = True
    message_type = 'none'
    message_category = 'message'

    def setUp(self):
        self.message = messaging.Message()

    def test_two_instances_are_equal_if_body_is_the_same(self):
        msg1 = messaging.Message(1, 2, 3)
        msg2 = messaging.Message(1, 2, 3)
        self.assertNotEqual(id(msg1), id(msg2))
        self.assertEqual(msg1, msg2)
        
    def test_returns_correct_boolean_value(self):
        if self.boolean_value:
            self.assertTrue(self.message)
        else:
            self.assertFalse(self.message)
    
    def test_message_has_the_correct_type(self):
        self.assertEqual(self.message.type, self.message_type)

    def test_message_has_the_correct_category(self):
        self.assertEqual(self.message.category, self.message_category)


class TestMessageCommand(TestMessage):
    message_type = 'command'
    message_category = 'message'
    
    def setUp(self):
        self.kwds = dict(test_status_kwds)
        self.message = messaging.MessageCommand('test_command')

    def test_body_content_has_the_custom_keys(self):
        self.assertEqual(self.message.body['content'], {'parameters':{}})
        self.assertEqual(self.message.body['name'], 'test_command')
            


class TestMessageRpc(TestMessage):
    message_type = 'command'
    message_category = 'rpc'
    
    def setUp(self):
        self.kwds = dict(test_status_kwds)
        self.message = messaging.RpcCommand('test_command')

    def test_body_content_has_the_custom_keys(self):
        self.assertEqual(self.message.body['content'], {'parameters':{}})
        self.assertEqual(self.message.body['name'], 'test_command')


class TestMessageStatus(TestMessage):
    message_type = 'status'
    message_category = 'message'
    
    def setUp(self):
        status = messaging.Fingerprint(**test_status_kwds)
        self.message = messaging.MessageStatus('test_status')


class TestMessageResult(TestMessage):
    message_type = 'result'
    message_category = 'message'
    result_type = 'success'
    
    def setUp(self):
        self.message = messaging.MessageResult('test_value', 'test_message')

    def test_body_content_has_the_custom_keys(self):
        self.assertEqual(self.message.body['content'], {'type':self.result_type,
            'value':'test_value', 'message':'test_message'})
            

class TestMessageResultError(TestMessageResult):
    message_type = 'result'
    message_category = 'message'
    result_type = 'error'
    boolean_value = False

    def setUp(self):
        self.message = messaging.MessageResultError('test_message')
    
    def test_body_content_has_the_custom_keys(self):
        self.assertEqual(self.message.body['content'], {'type':self.result_type,
            'value':None, 'message':'test_message'})


class TestMessageResultException(TestMessageResult):
    message_type = 'result'
    message_category = 'message'
    result_type = 'exception'
    boolean_value = False

    def setUp(self):
        self.message = messaging.MessageResultException('test_name', 'test_message')

    def test_body_content_has_the_custom_keys(self):
        self.assertEqual(self.message.body['content'], {'type':self.result_type,
            'value':'test_name', 'message':'test_message'})


class CustomExchange(messaging.Exchange):
    name = 'custom_exchange'
    exchange_type = 'fanout'
    passive = True
    durable = False
    auto_delete = True


class TestExchange(unittest.TestCase):
    def setUp(self):
        self.exchange = CustomExchange()
    
    def test_exchange_returns_correct_parameters(self):
        d = self.exchange.parameters
        self.assertEqual(d['exchange'], 'custom_exchange')
        self.assertEqual(d['exchange_type'], 'fanout')
        self.assertEqual(d['passive'], True)
        self.assertEqual(d['durable'], False)
        self.assertEqual(d['auto_delete'], True)




########################
## Generic producer


class MockChannel(object):
    # This is a mock of a RabbitMQ channel.
    
    def __init__(self):
        # This stores queues and messages routed to them
        # {queue:[messages]}
        self._queues = {}
        
        # This stores the queue bindings with exchanges and routing keys
        # {exchange:[(routing_key,queue)]}
        self._bindings = {}
        
        # The exchanges declared on this channel
        # {name:exchange}
        self._exchanges = {}

        # This stores messages sent to exchanges
        # {name:[messages]}
        self._exchange_messages = {}
        
        # This flag enables RPC auto answer
        self._rpc_auto_answer = False
        self._rpc_auto_answer_message = {}
        
    def get_last_message(self, queue):
        return self._queues[queue].pop()

    def get_last_sent_message(self, exchange):
        return self._exchange_messages[exchange].pop()

    def _reset(self):
        self._queues = {}
        self._bindings = {}
        self._exchanges = {}
        self._exchange_messages = {}
        self._rpc_auto_answer = False
        self._rpc_auto_answer_message = {}

    def _process_all(self):
        for exchange, messages in self._exchange_messages.iteritems():
            # This treats all exchanges as direct at the moment
            
            # Get the bindings of this exchange
            bindings = self._bindings[exchange]
            
            # Messages that have been delivered
            processed_messages = []
            
            if self._rpc_auto_answer:
                tmp_messages = messages[:]
                for index in range(len(tmp_messages)):
                    message = tmp_messages[index]
                    # If there is a message with a reply_to set to a known
                    # queue extract it and put an answer in messages
                    if message['properties'].reply_to in self._queues:
                        messages.pop(index)

                        answer = {'body':messaging.JsonEncoder.encode(\
                                    self._rpc_auto_answer_message.body),
                                'exchange':message['exchange'],
                                'properties':message['properties'],
                                'routing_key':message['properties'].reply_to}
                        
                        messages.append(answer)
            
            for message in messages:
                if message['routing_key'] in self._queues:
                    self._queues[message['routing_key']].append(message['body'])
                    processed_messages.append(message)
                    continue
                    
                for routing_key, queue in bindings:
                    if message['routing_key'] == routing_key:
                        self._queues[queue].append(message['body'])
                        processed_messages.append(message)
                    

            # Messages that have not been delivered
            unprocessed_messages = []
            for message in messages:
                if message not in processed_messages:
                    unprocessed_messages.append(message)

            # Next execution shall find the message we left
            self._exchange_messages[exchange] = unprocessed_messages

    def exchange_declare(self, **kwds):
        # This declares the exchange on the channel
        self._exchanges[kwds['exchange']] = kwds
        self._bindings[kwds['exchange']] = []
            
    def basic_consume(self, callback, queue):
        # This is supposed to fetch messages from the given queue
        # and call the given callback passing the message
        message = self.get_last_message(queue)
        callback(self, mock.Mock(), mock.Mock(), message)
    
    def start_consuming(self, *args, **kwds):
        # In the original object that starts the callback call
        pass
        
    def stop_consuming(self, *args, **kwds):
        # In the original object that stops the callback call
        pass
        
    def basic_qos(self, *args, **kwds):
        # This is supposed to set Quality Of Service flags
        pass

    def queue_declare(self, queue=None, exclusive=True, auto_delete=True):
        # This method declares the given queue on the channel.
        # This mimics the real behaviour by generating a queue on the fly
        # if no queue name is given
        result = mock.Mock()
        if queue is not None:
            result.method.queue = queue
        else:
            result.method.queue = str(time.time())
        
        if result.method.queue not in self._queues:
            self._queues[result.method.queue] = []
        return result
        
    def basic_publish(self, body, exchange, properties, routing_key):
        # If the routing key is the name of a queue directly deliver the
        # message to that queue without passing through the exchange
        if exchange not in self._exchange_messages:
            self._exchange_messages[exchange] = []
        
        self._exchange_messages[exchange].append({'body':body,
                                                'exchange':exchange,
                                                'properties':properties,
                                                'routing_key':routing_key})
        
        self._process_all()

    def auto_rpc_answer(self, status=True, message={}):
        # This helper mimics the presence of a consumer on the channel
        # which answers RPC calls with the given message
        # passing status=True enables the auto-answer mechanism, status=False
        # disables it.
        self._rpc_auto_answer = status
        self._rpc_auto_answer_message = message


class TestGenericProducer(unittest.TestCase):
    @mock.patch('pika.BlockingConnection')
    @mock.patch('pika.PlainCredentials')
    @mock.patch('pika.ConnectionParameters')
    def setUp(self, plain_credentials, connection_parameters,
            blocking_connection):
        plain_credentials.return_value = None
        connection_parameters.return_value = None
        blocking_connection.return_value.channel.return_value = MockChannel()
        self.producer = messaging.GenericProducer()

    def check_last_message(self, body, routing_key, exchange,
            properties_content_type):
        last_message = self.producer.channel.get_last_message()
        self.producer.channel._reset()
        self.assertEqual(last_message['body'], body,
            "Expected %s, found %s" %(body, last_message['body']))
        self.assertEqual(last_message['routing_key'], routing_key,
            "Expected %s, found %s" %(routing_key, last_message['routing_key']))
        self.assertEqual(last_message['exchange'], exchange,
            "Expected %s, found %s" %(exchange, last_message['exchange']))
        self.assertEqual(last_message['properties'].content_type,
            properties_content_type)

    def check_last_sent_message(self, body, routing_key, exchange,
            properties_content_type):
        last_message = self.producer.channel.get_last_sent_message(exchange)
        self.producer.channel._reset()
        self.assertEqual(last_message['body'], body,
            "Expected %s, found %s" %(body, last_message['body']))
        self.assertEqual(last_message['routing_key'], routing_key,
            "Expected %s, found %s" %(routing_key, last_message['routing_key']))
        self.assertEqual(last_message['exchange'], exchange,
            "Expected %s, found %s" %(exchange, last_message['exchange']))
        self.assertEqual(last_message['properties'].content_type,
            properties_content_type)

    def test_build_message(self):
        message = messaging.Message(1, 2, 'str', name='a_name')
        self.assertEqual(message.body['content'], {'args':(1, 2, 'str'), 
            'kwds':{'name':'a_name'}})

    def test_returns_correct_message_properties(self):
        props = self.producer._build_message_properties()
        self.assertEqual(props.content_type, 'application/json')
    
    def test_returns_correct_rpc_properties(self):
        props = self.producer._build_rpc_properties()
        self.assertEqual(props.content_type, 'application/json')
    
    def test_correctly_encodes_message(self):
        message = {'message':'a test'}
        encoded_message = self.producer._encode(message)
        decoded_messsge = self.producer.encoder.decode(encoded_message)
        self.assertEqual(message, decoded_messsge)
    
    def test_correctly_builds_message(self):
        message = messaging.Message(3, 'test', adict={'number':25})
        self.assertEqual(message.body, messaging.Message(3, 'test',
            adict={'number':25}).body)

    def test_low_level_message_creation_and_delivering_works(self):
        self.producer._message_send(3,
                                    'test', 
                                    adict={'number':25}, 
                                    _key="a_test_routing_key", 
                                    _callable=messaging.Message)
        
        message = messaging.Message(3,
                                    'test',
                                    adict={'number':25})
        message.fingerprint(**messaging.Fingerprint().as_dict())
        body = messaging.JsonEncoder().encode(message.body)
        self.check_last_sent_message(body,
                                    'a_test_routing_key', 
                                    self.producer.default_exchange.name, 
                                    'application/json')
    
    def low_level_rpc_helper(self):
        return self.producer._rpc_send(3,
                                    'test', 
                                    adict={'number':25}, 
                                    _key="a_test_routing_key", 
                                    _callable=messaging.Message)
        
    def test_low_level_succesful_rpc_creation_and_delivering_works(self):
        self.producer.channel.auto_rpc_answer(status=True,
            message=messaging.MessageResult(value=True,
                                            message="test_error_message"))
        rpc_answer = self.low_level_rpc_helper()
        self.producer.channel.auto_rpc_answer(status=False)
        self.assertTrue(rpc_answer.body['content']['value'])

    def test_low_level_unsuccesful_rpc_creation_and_delivering_works(self):
        self.producer.channel.auto_rpc_answer(status=True,
            message=messaging.MessageResultError(message="test_error_message"))
        rpc_answer = self.low_level_rpc_helper()
        self.producer.channel.auto_rpc_answer(status=False)
        self.assertEqual(rpc_answer.body['content']['value'], None)

    def test_low_level_rpc_queue_is_correct(self):
        self.producer.channel.auto_rpc_answer(status=True,
            message=messaging.MessageResult(value=True,
                                            message="test_error_message"))
        rpc_queue = self.producer._rpc_send(3, 'test',
                                            adict={'number':25},
                                            _key="a_test_routing_key",
                                            _queue_only=True,
                                            _callable=messaging.Message)
        rpc_answer = self.low_level_rpc_helper()
        self.producer.channel.auto_rpc_answer(status=False)
        self.assertTrue(rpc_queue)
    
    def test_high_level_message_creation_and_delivering_works(self):
        self.producer.message(3,
                            'test',
                            adict={'number':25},
                            _key="a_test_routing_key")
        
        message = messaging.Message(3,
                                    'test',
                                    adict={'number':25})
        
        message.fingerprint(**messaging.Fingerprint().as_dict())
        body = messaging.JsonEncoder().encode(message.body)
        self.check_last_sent_message(body,
                                'a_test_routing_key',
                                self.producer.default_exchange.name,
                                'application/json')
    
    def test_forwarding_works(self):
        message = messaging.Message(3, 'test', adict={'number':25})
        self.producer.forward(message.body, _key="a_test_routing_key")
        body = messaging.JsonEncoder().encode(message.body)
        self.check_last_sent_message(body,
                                    'a_test_routing_key', 
                                    self.producer.default_exchange.name, 
                                    'application/json')
        

class TestGenericConsumer(unittest.TestCase):
    @mock.patch('pika.BlockingConnection')
    @mock.patch('pika.PlainCredentials')
    @mock.patch('pika.ConnectionParameters')
    def setUp(self, plain_credentials, connection_parameters,
            blocking_connection):
        plain_credentials.return_value = None
        connection_parameters.return_value = None
        blocking_connection.return_value.channel.return_value = MockChannel()
        self.consumer = messaging.GenericConsumer()

    def test_init(self):
        self.assertEqual(self.consumer.eqk, [])
        
    # TODO: Consider adding some tests... =)

if __name__ == '__main__':
	unittest.main()
