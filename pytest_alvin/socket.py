import re
import pytest

import socket


_orig_socket_connect = socket.socket.connect


# need to improve this regex in future, 172.* is sometimes external IP
ALLOWED_HOSTS_REGEX = re.compile(r'(127)|(172)')


class SocketConnectBlocked(RuntimeError):
    pass


def host_from_address(address):
    host = address[0]
    if isinstance(host, str):
        return host


def host_from_connect_args(args):
    address = args[0]

    if isinstance(address, tuple):
        return host_from_address(address)


def guarded_connect(inst, *args, **kwargs):
    host = host_from_connect_args(args)
    if host and ALLOWED_HOSTS_REGEX.match(host):
        return _orig_socket_connect(inst, *args, **kwargs)

    raise SocketConnectBlocked(
        f'Tried to access socket connection to {host}, not allowed in unit tests'
    )


def disable_socket():
    socket.socket.connect = guarded_connect


def enable_socket():
    socket.socket.connect = _orig_socket_connect


@pytest.fixture
def socket_disabled():
    disable_socket()
    yield
    enable_socket()
