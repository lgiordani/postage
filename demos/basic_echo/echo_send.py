from postage import messaging
import echo_shared


class EchoProducer(messaging.GenericProducer):
    eks = [(echo_shared.EchoExchange, 'echo-rk')]

producer = EchoProducer()
producer.message_echo("A test message")
