import tornado.web


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__()
        self.data: dict = {}

    def route(self, path: str):
        def __add_route(handler: tornado.web.RequestHandler):
            self.add_handlers(r".*", [(path, handler, self.data)])

        return __add_route

    def add_data(self, data: dict):
        for k, v in data.items():
            self.data[k] = v

    def build(self):
        pass


app = Application()
