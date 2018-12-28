import os
import time
import shutil
import tempfile
import weakref
import atexit
import functools

import docker


start_time = int(time.time())
counter = 0
client = docker.from_env(version='auto')


def _remove_weakref(service):
    # dereferece weakref
    service = service()
    if service is not None:
        service.remove()



class Service(object):
    """Base class for docker based services"""
    timeout = 30.0
    name = 'service'

    def __init__(self, image, wait=False, **kwargs):
        global counter

        self.client = client

        kwargs.setdefault('detach', True)
        name = 'tmp_{}_{}_{}'.format(start_time, self.name, counter)
        kwargs.setdefault('name', name)
        counter += 1

        kwargs.setdefault('volumes', {})
        self.share = tempfile.mkdtemp(name)
        kwargs['volumes'][self.share] = {'bind': self.share, 'mode': 'rw'}

        atexit_callback = functools.partial(_remove_weakref, weakref.ref(self))
        atexit.register(atexit_callback)
        self.container = client.containers.run(image, **kwargs)
        if wait:
            self.wait()

    def inspect(self):
        """get docker inspect data for container"""
        return self.client.api.inspect_container(self.container.id)

    def ip_address(self):
        return self.inspect()['NetworkSettings']['IPAddress']

    def wait(self, timeout=None):
        if timeout is None:
            timeout = self.timeout

        start = time.time()
        while not self.check_ready() and time.time() - start < timeout:
            time.sleep(0.1)

    def remove(self):
        # this must be safe to call during interpreter shutdown
        # object might already disintegrate
        if hasattr(self, 'container'):
            try:
                self.container.remove(force=True, v=True)
            except docker.errors.NotFound:
                pass

        if os.path.exists(self.share):
            shutil.rmtree(self.share)

    def __del__(self):
        try:
            self.remove()
        except:
            # on interpreter shutdown deleting container will
            # fail as the docker client is already breaking apart.
            # the atexit callback will be called earlier, taking
            # care of this case
            pass


class HTTPServer(Service):
    protocol = 'http'
    port = '80'

    def check_ready(self):
        import requests

        ip = self.ip_address()
        url = '{}://{}:{}'.format(self.protocol, ip, self.port)

        try:
            requests.get(url)
            return True
        except requests.exceptions.ConnectionError:
            return False

