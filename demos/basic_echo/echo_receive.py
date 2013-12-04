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
