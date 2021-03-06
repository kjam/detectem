import re
import time
import sys
import logging
import json

from contextlib import contextmanager

import docker
import requests

from detectem.exceptions import NotNamedParameterFound
from detectem.settings import SPLASH_URL, SETUP_SPLASH, DOCKER_SPLASH_IMAGE


logger = logging.getLogger('detectem')


def get_most_complete_version(versions):
    """ Return the most complete version.

    i.e. `versions=['1.4', '1.4.4']` it returns '1.4.4' since it's more complete.
    """
    if not versions:
        return

    return max(versions)


def check_presence(text, matchers):
    for matcher in matchers:
        if isinstance(matcher, str):
            v = re.search(matcher, text, flags=re.DOTALL)
            if v:
                return True
        elif callable(matcher):
            v = matcher(text)
            if v:
                return True

    return False


def extract_data(text, matchers, parameter):
    for matcher in matchers:
        if isinstance(matcher, str):
            v = re.search(matcher, text, flags=re.DOTALL)
            if v:
                try:
                    return v.group(parameter)
                except IndexError:
                    raise NotNamedParameterFound(
                        'Parameter %s not found in regexp' %
                        parameter
                    )
        elif callable(matcher):
            v = matcher(text)
            if v:
                return v


def extract_version(text, matchers):
    return extract_data(text, matchers, 'version')


def extract_name(text, matchers):
    return extract_data(text, matchers, 'name')

def extract_version_from_headers(headers, matchers):
    for matcher_name, matcher_value in matchers:
        for header in headers:
            if header['name'] == matcher_name:
                v = extract_version(header['value'], [matcher_value])
                if v:
                    return v


@contextmanager
def docker_container():
    """ Start a container for doing requests.
    If it doesn't exist, it creates the container named 'splash-detectem'.

    """
    if SETUP_SPLASH:
        docker_cli = docker.from_env()
        container_name = 'splash-detectem'

        try:
            container = docker_cli.containers.get(container_name)
        except docker.errors.NotFound:
            try:
                docker_cli.images.get(DOCKER_SPLASH_IMAGE)
            except docker.errors.ImageNotFound:
                logger.error(
                    "%(evar)s not found. Please install the docker image or "
                    "set an image using DOCKER_SPLASH_IMAGE environment variable.",
                    {'evar': DOCKER_SPLASH_IMAGE}
                )
                sys.exit(-1)

            # Create docker container
            container = docker_cli.containers.create(
                name=container_name,
                image=DOCKER_SPLASH_IMAGE,
                ports={
                    '5023/tcp': 5023,
                    '8050/tcp': 8050,
                    '8051/tcp': 8051,
                },
            )

        if container.status != 'running':
            container.start()
            time.sleep(1)

    # Send request to delete cache
    requests.post('{}/_gc'.format(SPLASH_URL))

    yield


def print_error_message(error_dict, format):
    if format == 'json':
        print(json.dumps(error_dict))
    else:
        print(error_dict)
