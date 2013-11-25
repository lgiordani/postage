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
                (shared_queue, 'echo'),
                (private_queue, 'echo-fanout')
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
