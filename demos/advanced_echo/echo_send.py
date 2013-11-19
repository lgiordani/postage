from postage import messaging
import echo_shared

fingerprint = messaging.Fingerprint('echo_send', 'application').as_dict()
producer = echo_shared.EchoProducer(fingerprint)
producer.message_echo("A test message")
