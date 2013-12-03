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
