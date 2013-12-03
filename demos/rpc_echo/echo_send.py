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
