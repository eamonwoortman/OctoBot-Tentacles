#  Drakkar-Software OctoBot-Tentacles
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import logging
import os
from threading import Thread

import flask
from pyngrok import ngrok
from werkzeug.serving import make_server
from flask import request, abort

from octobot_commons.logging.logging_util import set_logging_level
from octobot_services.constants import CONFIG_WEBHOOK, CONFIG_CATEGORY_SERVICES, CONFIG_SERVICE_INSTANCE, \
    CONFIG_NGROK_TOKEN, ENV_WEBHOOK_ADDRESS, CONFIG_WEB_IP, ENV_WEBHOOK_PORT, CONFIG_WEB_PORT, \
    DEFAULT_WEBHOOK_SERVER_PORT, DEFAULT_WEBHOOK_SERVER_IP
from octobot_services.services.abstract_service import AbstractService


class WebHookService(AbstractService):
    LOGGERS = ["pyngrok.ngrok", "pyngrok.process", "werkzeug"]

    def get_fields_description(self):
        return {
            CONFIG_NGROK_TOKEN: "The ngrok token used to expose the webhook to internet."
        }

    def get_default_value(self):
        return {
            CONFIG_NGROK_TOKEN: ""
        }

    def __init__(self):
        super().__init__()
        self.ngrok_public_url = ""
        self.webhook_public_url = ""

        self.service_feed_webhooks = {}

        self.webhook_app = None
        self.webhook_host = None
        self.webhook_port = None
        self.webhook_server = None
        self.webhook_server_context = None
        self.webhook_server_thread = None

    @staticmethod
    def is_setup_correctly(config):
        return CONFIG_WEBHOOK in config[CONFIG_CATEGORY_SERVICES] \
               and CONFIG_SERVICE_INSTANCE in config[CONFIG_CATEGORY_SERVICES][CONFIG_WEBHOOK]

    @staticmethod
    def get_is_enabled(config):
        return True

    def has_required_configuration(self):
        return CONFIG_CATEGORY_SERVICES in self.config \
               and CONFIG_WEBHOOK in self.config[CONFIG_CATEGORY_SERVICES] \
               and self.check_required_config(self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEBHOOK])

    def get_required_config(self):
        return [CONFIG_NGROK_TOKEN]

    def get_endpoint(self) -> None:
        return ngrok

    def get_type(self) -> None:
        return CONFIG_WEBHOOK

    @staticmethod
    def connect(port, protocol="http") -> str:
        """
        Create a new ngrok tunnel
        :param port: the tunnel local port
        :param protocol: the protocol to use
        :return: the ngrok url
        """
        return ngrok.connect(port, protocol)

    def subscribe_feed(self, service_feed_name, service_feed_callback) -> str:
        """
        Subscribe a service feed to the webhook
        :param service_feed_name: the service feed name
        :param service_feed_callback: the service feed callback reference
        :return: the service feed webhook url
        """
        if service_feed_name not in self.service_feed_webhooks:
            self.service_feed_webhooks[service_feed_name] = service_feed_callback
            return f"{self.webhook_public_url}/{service_feed_name}"
        raise KeyError(f"Service feed has already subscribed to a webhook : {service_feed_name}")

    def _prepare_webhook_server(self):
        try:
            self.webhook_server = make_server(host=self.webhook_host,
                                              port=self.webhook_port,
                                              threaded=True,
                                              app=self.webhook_app)
            self.webhook_server_context = self.webhook_app.app_context()
            self.webhook_server_context.push()
        except OSError as e:
            self.webhook_server = None
            self.get_logger().exception(f"Fail to start webhook : {e}")

    def _load_webhook_routes(self) -> None:
        @self.webhook_app.route('/')
        def index():
            """
            Route to check if webhook server is online
            """
            return ''

        @self.webhook_app.route('/webhook/<webhook_name>', methods=['POST'])
        def webhook(webhook_name):
            if webhook_name in self.service_feed_webhooks:
                if request.method == 'POST':
                    self.service_feed_webhooks[webhook_name](request.get_data(as_text=True))
                    return '', 200
                abort(400)
            else:
                self.logger.warning(f"Received unknown request from {webhook_name}")
                abort(500)

    def run_webhook_server(self):
        if self.webhook_server:
            self.webhook_server.serve_forever()

    async def prepare(self) -> None:
        set_logging_level(self.LOGGERS, logging.WARNING)
        ngrok.set_auth_token(self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEBHOOK][CONFIG_NGROK_TOKEN])

        self.webhook_app = flask.Flask(__name__)
        try:
            self.webhook_host = os.getenv(ENV_WEBHOOK_ADDRESS, self.config[CONFIG_CATEGORY_SERVICES]
                                          [CONFIG_WEBHOOK][CONFIG_WEB_IP])
        except KeyError:
            self.webhook_host = os.getenv(ENV_WEBHOOK_ADDRESS, DEFAULT_WEBHOOK_SERVER_IP)
        try:
            self.webhook_port = int(os.getenv(ENV_WEBHOOK_PORT, self.config[CONFIG_CATEGORY_SERVICES]
            [CONFIG_WEBHOOK][CONFIG_WEB_PORT]))
        except KeyError:
            self.webhook_port = int(os.getenv(ENV_WEBHOOK_PORT, DEFAULT_WEBHOOK_SERVER_PORT))

        try:
            self._prepare_webhook_server()
            self._load_webhook_routes()
            self.ngrok_public_url = self.connect(self.webhook_port, protocol="http")
            self.webhook_public_url = f"{self.ngrok_public_url}/webhook"
            self.webhook_server_thread = Thread(target=self.run_webhook_server)
            self.webhook_server_thread.start()
        except Exception as e:
            self.logger.exception(e, True, f"Error when running webhook service: ({e})")

    def get_successful_startup_message(self):
        return f"Global webhook url = {self.ngrok_public_url}/webhook", True

    def _prepare_stop(self):
        self.webhook_server.server_close()

    def stop(self):
        self._prepare_stop()
        self.webhook_server.shutdown()