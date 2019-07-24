#!/usr/bin/env python2
"""
Taken from: http://code.activestate.com/recipes/576655-wait-for-network-service-to-appear/
"""
import errno
import socket
import sys


def wait_net_service(server, port, timeout=None):
    """ Wait for network service to appear
        @param timeout: in seconds, if None or 0 wait forever
        @return: True of False, if timeout is None may return only True or
                 throw unhandled network exception
    """
    s = socket.socket()
    if timeout:
        from time import time as now
        # time module is needed to calc timeout shared between two exceptions
        end = now() + timeout

    while True:
        try:
            if timeout:
                next_timeout = end - now()
                if next_timeout < 0:
                    return False
                else:
                    s.settimeout(next_timeout)

            s.connect((server, port))

        except socket.timeout:
            # this exception occurs only if timeout is set
            if timeout:
                return False

        except socket.error:
            # just ignore anything else until we run into timeout
            pass
        else:
            s.close()
            return True


if __name__ == "__main__":
    if len(sys.argv) not in [3, 4]:
        print "Usage: %s <host> <port> [<timeout>]" % (sys.argv[0])
        sys.exit(1)

    timeout = 60
    if len(sys.argv) == 4:
        timeout = int(sys.argv[3])

    if wait_net_service(sys.argv[1], int(sys.argv[2]), timeout):
        sys.exit(0)
    else:
        sys.exit(1)
