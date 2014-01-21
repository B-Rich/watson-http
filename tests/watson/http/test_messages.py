# -*- coding: utf-8 -*-
from copy import copy
from io import BytesIO, BufferedReader, StringIO
import json
from pytest import raises
from watson.http.messages import Response, Request, create_request_from_environ
from watson.http.cookies import CookieDict
from watson.http import sessions
from watson.common.datastructures import ImmutableMultiDict, MultiDict
from tests.watson.http.support import sample_environ, start_response


class TestRequest(object):

    def test_create(self):
        request = Request('get')
        assert request.method == 'GET'

    def test_create_invalid_headers(self):
        request = Request('get', headers={'Something': 'test'})
        assert request.headers.__len__() == 1

    def test_create_from_environ(self):
        environ = sample_environ()
        request = create_request_from_environ(environ)
        assert request.method == 'GET'
        assert request.is_method('GET')

    def test_create_put_from_environ(self):
        data = 'HTTP_REQUEST_METHOD=PUT'
        environ = sample_environ(REQUEST_METHOD='POST', CONTENT_LENGTH=len(data))
        environ['wsgi.input'] = BufferedReader(
            BytesIO(data.encode('utf-8')))
        request = create_request_from_environ(environ)
        assert request.post['HTTP_REQUEST_METHOD'] == 'PUT'
        assert request.is_method('PUT')

    def test_get_vars(self):
        environ = sample_environ(
            QUERY_STRING='blah=something&someget=test&arr[]=a&arr[]=b')
        request = create_request_from_environ(environ)
        assert request.get['blah'] == 'something'

    def test_is_xml_http_request(self):
        environ = sample_environ(HTTP_X_REQUESTED_WITH='XmlHttpRequest')
        request = create_request_from_environ(environ)
        assert request.is_xml_http_request()

    def test_is_secure(self):
        environ = sample_environ(HTTPS='HTTPS')
        environ['wsgi.url_scheme'] = 'https'
        request = create_request_from_environ(environ)
        assert str(request) == 'GET https://127.0.0.1/ HTTP/1.1\r\nHost: 127.0.0.1\r\nHttps: HTTPS\r\n\r\n'
        assert request.is_secure()

    def test_host(self):
        environ = sample_environ(HTTP_X_FORWARDED_FOR='10.11.12.13')
        request = create_request_from_environ(environ)
        assert request.host() == '10.11.12.13'

    def test_server(self):
        environ = sample_environ()
        request = create_request_from_environ(environ)
        assert request.server['PATH_INFO'] == '/'

    def test_cookies(self):
        environ = sample_environ(HTTP_COOKIE='test=something;')
        request = create_request_from_environ(environ)
        assert request.cookies['test'].value == 'something'

    def test_session(self):
        environ = sample_environ(HTTP_COOKIE='watson.session=123456;')
        request = create_request_from_environ(
            environ, 'watson.http.sessions.Memory')
        assert request.session.id == '123456'
        assert isinstance(request.session, sessions.Memory)

    def test_create_invalid(self):
        with raises(TypeError):
            Request('INVALID')

    def test_create_mutable(self):
        environ = sample_environ()
        data = 'HTTP_REQUEST_METHOD=PUT'
        environ['REQUEST_METHOD'] = 'POST'
        environ['CONTENT_LENGTH'] = len(data)
        environ['wsgi.input'] = BufferedReader(
            BytesIO(data.encode('utf-8')))
        request = create_request_from_environ(environ)
        new_request = copy(request)
        assert isinstance(request.post, ImmutableMultiDict)
        assert isinstance(new_request.post, MultiDict)

    def test_repr(self):
        environ = sample_environ()
        assert repr(create_request_from_environ(environ)
                    ) == '<watson.http.messages.Request method:GET url:http://127.0.0.1/>'

    def test_json_body(self):
        json_str = '{"test": [1, 2, 3]}'
        environ = sample_environ(CONTENT_TYPE='application/json; charset=utf-8',
                                 CONTENT_LENGTH=len(json_str),
                                 REQUEST_METHOD='put')
        environ['wsgi.input'] = BufferedReader(
            BytesIO(json_str.encode('utf-8')))
        request = create_request_from_environ(environ)
        json_output = json.loads(request.body)
        assert 'test' in json_output


class TestResponse(object):

    def test_create(self):
        response = Response(200, body='This is the body')
        assert response.body == 'This is the body'
        assert response.status_line == '200 OK'

    def test_output(self):
        response = Response(200, body='Something here')
        response.headers.add('Content-Type', 'text/html')
        string_output = "HTTP/1.1 200 OK\r\nContent-Length: 14\r\nContent-Type: text/html\r\n\r\nSomething here"
        raw_output = b'HTTP/1.1 200 OK\r\nContent-Length: 14\r\nContent-Type: text/html\r\n\r\nSomething here'
        assert str(response) == string_output
        assert response.raw() == raw_output

    def test_encoding(self):
        response = Response(200)
        assert response.encoding == 'utf-8'

    def test_encode_body(self):
        response = Response(200, body='Test')
        assert response(start_response) == [b'Test']

    def test_start(self):
        response = Response()
        status_line, headers = response.start()
        assert status_line == '200 OK'
        assert headers == [('Content-Length', '0')]

    def test_set_cookie(self):
        response = Response(200, body='Test')
        response.cookies.add('test', 'value')
        assert str(
            response) == "HTTP/1.1 200 OK\r\nContent-Length: 4\r\nSet-Cookie: test=value; Path=/\r\n\r\nTest"

    def test_set_new_cookie(self):
        response = Response(200)
        response.cookies = 'blah'
        assert isinstance(response.cookies, CookieDict)
