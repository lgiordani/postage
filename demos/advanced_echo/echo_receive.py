from postage import microthreads
from postage import messaging
import echo_shared

class EchoReceiveProcessor(messaging.MessageProcessor):
    def __init__(self, fingerprint):
        eqk = [
            (echo_shared.EchoExchange, [
                            ('echo-queue', 'echo'),
                            ]), 
            ]
        super(EchoReceiveProcessor, self).__init__(fingerprint, eqk, None, None)

    @messaging.MessageHandler('command', 'echo')
    def msg_echo(self, content):
        print content['parameters']

fingerprint = messaging.Fingerprint('echo_receive', 'controller').as_dict()

scheduler = microthreads.MicroScheduler()
scheduler.add_microthread(EchoReceiveProcessor(fingerprint))
for i in scheduler.main():
    pass
