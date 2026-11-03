"""Bound request bodies before parsing, including chunked requests."""
import asyncio
from uuid import uuid4
from starlette.responses import JSONResponse


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        maximum = 262144 if scope['path'] == '/api/v1/webhooks/paypal' else 65536
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    size += len(message.get('body', b''))
                    if size > maximum:
                        return await self.reject(scope, receive, send, 413, 'REQUEST_TOO_LARGE')
                    chunks.append(message.get('body', b''))
                    if not message.get('more_body', False):
                        break
        except TimeoutError:
            return await self.reject(scope, receive, send, 408, 'REQUEST_TIMEOUT')
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def reject(scope, receive, send, status, code):
        response = JSONResponse({'error': {'code': code, 'message': 'Request could not be accepted.',
            'request_id': 'req_'+uuid4().hex}}, status_code=status, headers={'Cache-Control': 'no-store'})
        await response(scope, receive, send)
