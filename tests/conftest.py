import sys
import socket

# Windows ephemeral port exhaustion or permission bug (WinError 10013) workaround for asyncio self-pipe
if sys.platform == "win32":
    _orig_socketpair = getattr(socket, "socketpair", None)
    _port_counter = 50200

    def _safe_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        global _port_counter
        for _ in range(500):
            _port_counter = 50200 + ((_port_counter - 50200 + 1) % 5000)
            port = _port_counter
            lsock = socket.socket(family, type, proto)
            try:
                lsock.bind(("127.0.0.1", port))
                lsock.listen(1)
                csock = socket.socket(family, type, proto)
                for offset in range(1, 10):
                    cport = port + offset
                    try:
                        csock.bind(("127.0.0.1", cport))
                        csock.connect(("127.0.0.1", port))
                        ssock, _ = lsock.accept()
                        lsock.close()
                        return ssock, csock
                    except OSError:
                        continue
                csock.close()
                lsock.close()
            except OSError:
                lsock.close()
                continue
        if _orig_socketpair:
            return _orig_socketpair(family, type, proto)
        raise OSError("Could not allocate socketpair on Windows")

    socket.socketpair = _safe_socketpair
