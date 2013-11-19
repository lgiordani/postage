from postage import messaging


class EchoExchange(messaging.Exchange):
    name = "echo-exchange"
    exchange_type = "direct"
    passive = False
    durable = True
    auto_delete = False


class EchoProducer(messaging.GenericProducer):
    eks = [(EchoExchange, 'echo')]
