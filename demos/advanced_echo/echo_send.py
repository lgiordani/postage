from postage import messaging
import echo_shared


class EchoProducer(messaging.GenericProducer):
    eks = [(echo_shared.EchoExchange, 'echo-rk')]


fingerprint = messaging.Fingerprint('echo_send', 'application').as_dict()
producer = EchoProducer(fingerprint)
producer.message_echo("A single test message")
producer.message_echo("A fanout test message", _key='echo-fanout-rk')
